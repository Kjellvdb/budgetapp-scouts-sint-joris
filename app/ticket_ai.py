"""Leest een foto van een kasticket uit met de Groq-API en geeft Expense-objecten terug."""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path
import re
from typing import Sequence
import io
from PIL import Image, ImageOps
from concurrent.futures import ThreadPoolExecutor
import collections
import threading
import time
from groq import Groq

from dotenv import load_dotenv

from app.common import AI_CATEGORIES, Expense, format_money, format_quantity, parse_date, parse_price

load_dotenv()

DEFAULT_MODEL = "qwen/qwen3.8-27b"   # overschrijfbaar via GROQ_MODEL in het .env-bestand
MAX_IMAGE_BYTES = 4 * 1024 * 1024    # limiet van Groq voor base64-afbeeldingen
MAX_IMAGES = 10
STRIP_RATIO = 1.0      # stroohoogte = breedte x 1.0
STRIP_OVERLAP = 0.12   # overlap tussen stroken
TARGET_WIDTH = 1000    # kleinere foto's worden hiertoe vergroot (leesbare tekst)
MAX_WIDTH = 1000       # grotere foto's worden hiertoe verkleind
MAX_STRIPS = 30        # maximum aantal API-aanroepen per ticket
TAIL_SIZE = 6          # aantal laatste regels van de vorige strook waarmee gededupliceerd wordt
DEFAULT_SLOTS = 2      # verwacht aantal stroken per minuut zolang er nog niets gemeten is

LAST_WARNING = ""      # controlemelding van de laatste uitlezing (leeg = alles klopt)

MAX_PARALLEL = 2           # met een tokenlimiet heeft meer tegelijk weinig zin
TOKENS_PER_MINUTE = 8000   # limiet van jouw model (zie Groq console > Limits)
LIMIT_SAFETY = 0.99        # we benutten maximaal 99% van de limiet
INITIAL_ESTIMATE = 2200    # geschat tokenverbruik per strook; wordt bijgesteld op basis van echt verbruik
MAX_WAIT = 180             # langer wachten dan dit (sec) = waarschijnlijk dagelijkse limiet: stoppen
MAX_TOTAL_WAIT = 600       # max totale tijd per strook (sec), inclusief wachten op de limiet


PROMPT = (
    "STROOK van een kassaticket/factuur (bv. Colruyt). Negeer regels die aan de boven- of onderrand afgesneden zijn.\n"
    "Per productregel (met artikelnummer): artikelnr (Art.Nr, cijfers), item, aantal (Hoev.), "
    "totale_prijs (kolom Bedrag, NIET eenheidsprijs), categorie ('Alcohol' bier/wijn, "
    "'Sterke Drank' likeur/whisky/gin/vodka, anders 'Algemeen').\n"
    "GEEN items: categoriekoppen (---- Zuivel), 'Suppl. kaderkorting', '(in prijs verrekend)', "
    "BTW-overzicht en totaalregels. Geen producten: lege lijst.\n"
    "Alleen als ze in DEZE strook staan (anders \"0\", of \"\" voor de datum): datum (DD/MM/JJJJ), "
    "leeggoed_totaal ('TOTAAL LEEGGOED'), btw_totaal (BTW-BEDRAG in euro uit regel 'BTW', kolom Totaal; "
    "niet 'Excl BTW', niet het %), totaal_goederen, totaal_te_betalen. "
    "Leeggoed en BTW nooit in items. Verzin niets.\n"
    "Antwoord enkel JSON, alle waarden als tekst tussen aanhalingstekens, punt als decimaalteken (\"5.65\"):\n"
    '{"datum":"","items":[{"artikelnr":"","item":"","aantal":"","totale_prijs":"","categorie":"Algemeen"}],'
    '"leeggoed_totaal":"0","btw_totaal":"0","totaal_goederen":"0","totaal_te_betalen":"0"}'
)


class TicketCancelled(Exception):
    """Het uitlezen werd afgebroken (venster of app gesloten)."""

class _TokenLimiter:
    """Houdt het tokenverbruik van de laatste 60 seconden bij en laat aanvragen wachten als het vol zit."""

    def __init__(self, per_minute: int):
        self.limit = per_minute
        self.lock = threading.Lock()
        self.events: collections.deque = collections.deque()  # [tijdstip, tokens]
        self.blocked_until = 0.0
        self.estimate = INITIAL_ESTIMATE
        self._seen: list[int] = []

    def _used(self, now: float) -> int:
        while self.events and now - self.events[0][0] >= 60:
            self.events.popleft()
        return sum(e[1] for e in self.events)

    def acquire(self, on_wait=None, cancel: "threading.Event | None" = None) -> list:
        """Wacht tot er ruimte is en reserveert dan het geschatte aantal tokens."""
        stop = cancel or threading.Event()
        while True:
            if stop.is_set():
                raise TicketCancelled()
            with self.lock:
                now = time.monotonic()
                used = self._used(now)
                if now < self.blocked_until:
                    wait = self.blocked_until - now
                elif not self.events or used + self.estimate <= self.limit:
                    event = [now, self.estimate]
                    self.events.append(event)
                    return event
                else:
                    wait = 60 - (now - self.events[0][0]) + 0.5
            if on_wait:
                on_wait(wait)
            if stop.wait(min(max(wait, 0.5), 3)):   # slaapt, maar wordt meteen wakker bij annuleren
                raise TicketCancelled()

    def record(self, event: list, actual: int | None) -> None:
        """Vervangt de schatting door het echte verbruik (0 bij een mislukte aanvraag)."""
        with self.lock:
            if actual is None:
                return
            event[1] = actual
            if actual > 0:
                self._seen.append(actual)
                recent = self._seen[-5:]
                self.estimate = int(sum(recent) / len(recent))

    def block(self, seconds: float) -> None:
        with self.lock:
            self.blocked_until = max(self.blocked_until, time.monotonic() + seconds + 0.5)


LIMITER = _TokenLimiter(int(TOKENS_PER_MINUTE * LIMIT_SAFETY))


def _retry_delay(exc: Exception) -> float | None:
    """Aantal seconden wachten bij een rate-limit-fout, of None als het een andere fout is."""
    text = str(exc)
    if getattr(exc, "status_code", None) != 429 and "rate_limit" not in text.lower() and "429" not in text:
        return None
    seconds = 0.0
    m = re.search(r"try again in\s+([0-9hms.\s]+)", text)
    if m:
        for val, unit in re.findall(r"([\d.]+)\s*(ms|h|m|s)", m.group(1)):
            seconds += float(val) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    return seconds or 20.0


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # herstel: bedragen zoals  "totale_prijs": 5,65,  ->  "totale_prijs": "5,65",
        fixed = re.sub(r'(:\s*)(-?\d+,\d+)(\s*[,}\]])', r'\1"\2"\3', text)
        return json.loads(fixed)


def _strip_parts(image_path: str) -> list[dict]:
    """Knipt een foto in overlappende, vergrote stroken (als image_url-onderdelen)."""
    path = Path(image_path)
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = img.size
    target = TARGET_WIDTH if w < TARGET_WIDTH else min(w, MAX_WIDTH)
    if target != w:
        img = img.resize((target, int(h * target / w)), Image.LANCZOS)
        w, h = img.size

    strip_h = int(w * STRIP_RATIO)
    step = int(strip_h * (1 - STRIP_OVERLAP))
    tops, top = [], 0
    while True:
        if top + strip_h >= h:
            tops.append(max(0, h - strip_h))
            break
        tops.append(top)
        top += step

    parts = []
    for top in tops:
        buf = io.BytesIO()
        img.crop((0, top, w, min(top + strip_h, h))).save(buf, "JPEG", quality=88)
        data = buf.getvalue()
        if len(data) > MAX_IMAGE_BYTES:
            raise RuntimeError(f"Een deel van '{path.name}' is te groot voor de AI. Verklein de foto.")
        b64 = base64.b64encode(data).decode("utf-8")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return parts


def _fmt_time(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}min {seconds % 60:02d}s"


def extract_expenses_from_image(image_paths: "str | Path | Sequence[str]", progress=None,
                                cancel: "threading.Event | None" = None) -> list[Expense]:
    """Leest één of meerdere foto's die samen één ticket vormen, strook per strook."""
    cancel = cancel or threading.Event()
    global LAST_WARNING
    LAST_WARNING = ""

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Geen GROQ_API_KEY gevonden in de .env file.")

    paths = [str(image_paths)] if isinstance(image_paths, (str, Path)) else [str(p) for p in image_paths]
    if not paths:
        raise RuntimeError("Geen afbeeldingen opgegeven.")
    if len(paths) > MAX_IMAGES:
        raise RuntimeError(f"Maximaal {MAX_IMAGES} foto's per ticket.")

    strips: list[dict] = []
    for p in paths:
        strips.extend(_strip_parts(p))
    if len(strips) > MAX_STRIPS:
        raise RuntimeError(f"Het ticket levert {len(strips)} stroken op (maximaal {MAX_STRIPS}). "
                           "Gebruik minder of kleinere foto's.")

    client = Groq(api_key=api_key, max_retries=0, timeout=30)
    model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    totals = {"leeggoed_totaal": 0.0, "btw_totaal": 0.0, "totaal_goederen": 0.0, "totaal_te_betalen": 0.0}
    rows: list[dict] = []
    found_date = None
    prev_tail: list[tuple] = []

    done = [0]
    total = len(strips)

    def say(text: str) -> None:
        if progress:
            progress(text)

    finish_times: list[float] = []
    peak_slots = [DEFAULT_SLOTS]

    def note_finished() -> None:
        now = time.monotonic()
        finish_times.append(now)
        peak_slots[0] = max(peak_slots[0], sum(1 for t in list(finish_times) if now - t < 60))

    def eta_seconds() -> float:
        """Schat hoelang het nog duurt tot ALLE resterende stroken klaar zijn."""
        remaining = total - done[0]
        if remaining <= 0:
            return 0.0
        now = time.monotonic()
        window = collections.deque(t - now for t in sorted(finish_times) if now - t < 60)
        slots = max(peak_slots[0], len(window), 1)
        t = 0.0
        for _ in range(remaining):
            while window and window[0] <= t - 60:
                window.popleft()
            while len(window) >= slots:
                t = max(t, window[0] + 60)
                window.popleft()
            window.append(t)
        return t + 3   # + de duur van de laatste aanvraag

    def ask(content: list[dict], json_mode: bool):
        kwargs = {"model": model, "messages": [{"role": "user", "content": content}],
                  "temperature": 0, "reasoning_effort": "none", "max_completion_tokens": 1200}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        deadline = time.monotonic() + MAX_TOTAL_WAIT
        while True:
            event = LIMITER.acquire(
                on_wait=lambda w: say(
                    f"⏸ Wachten op AI limiet... Nog ± {_fmt_time(max(eta_seconds(), w))}"
                    f" ({done[0]}/{total} klaar)"),
                cancel=cancel)
            if cancel.is_set():
                LIMITER.record(event, 0)
                raise TicketCancelled()
            t_call = time.monotonic()
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001
                LIMITER.record(event, 0)
                if "reasoning_effort" in kwargs and "reasoning_effort" in str(exc):
                    kwargs.pop("reasoning_effort")  # model weigert de parameter: opnieuw zonder
                    continue
                wait = _retry_delay(exc)
                if wait is None:
                    transient = ((getattr(exc, "status_code", None) or 0) >= 500
                                 or "Connection" in type(exc).__name__ or "Timeout" in type(exc).__name__)
                    if transient and time.monotonic() < deadline:
                        if cancel.wait(2):  # korte storing: opnieuw proberen
                            raise TicketCancelled()
                        continue
                    raise
                if wait > MAX_WAIT or time.monotonic() + wait > deadline:
                    raise RuntimeError(
                        f"Limiet van Groq bereikt (probeer opnieuw over ± {int(wait // 60) + 1} min): {exc}") from exc
                LIMITER.block(wait)
                continue
            usage = getattr(response, "usage", None)
            LIMITER.record(event, getattr(usage, "total_tokens", None))
            return response

    def fetch(args: tuple[int, dict]):
        if cancel.is_set():
            raise TicketCancelled()
        i, part = args
        content = [
            {"type": "text", "text": PROMPT},
            {"type": "text", "text": f"Strook {i} van {total}:"},
            part,
        ]
        try:
            response = ask(content, json_mode=True)
        except Exception as exc:  # noqa: BLE001
            if "json_validate_failed" not in str(exc):
                raise
            response = ask(content, json_mode=False)
        done[0] += 1
        note_finished()
        remaining = total - done[0]
        say(f"⏳ AI leest het ticket uit... "
            + (f"Nog ± {_fmt_time(eta_seconds())} " if remaining else "")
            + (f"({done[0]}/{total} klaar)"))
        return _parse_json(response.choices[0].message.content or "")

    t0 = time.monotonic()
    say(f"⏳ AI leest het ticket uit... (0/{total} klaar)")
    pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
    try:
        results = list(pool.map(fetch, enumerate(strips, start=1)))
    except BaseException:
        cancel.set()                # laat alle overige stroken meteen stoppen
        raise
    finally:
        pool.shutdown(wait=False)   # niet blijven hangen op lopende aanvragen

    for data in results:
        if isinstance(data, dict):
            m = re.search(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", str(data.get("datum") or ""))
            found_date = found_date or (parse_date(m.group(0).replace(".", "/").replace("-", "/")) if m else None)
        items = data if isinstance(data, list) else data.get("items", [])
        if isinstance(data, dict):
            for key in totals:
                value = parse_price(data.get(key)) or 0.0
                if value and not totals[key]:
                    totals[key] = value

        tail = list(prev_tail)   # regels van de vorige strook, waarmee we de overlap wegfilteren
        keys_this: list[tuple] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("item") or "").strip()
            if not name or name.lower() in ("leeggoed", "btw"):
                continue
            artnr = re.sub(r"\D", "", str(item.get("artikelnr") or ""))
            price = parse_price(item.get("totale_prijs")) or 0.0
            qty = format_quantity(item.get("aantal")) or "1"
            key = (artnr or name.lower()[:12], qty, round(price, 2))
            keys_this.append(key)
            if key in tail:          # zelfde regel stond al in de overlap van de vorige strook
                tail.remove(key)
                continue
            category = item.get("categorie")
            rows.append({"name": name, "qty": qty, "price": price,
                         "cat": category if category in AI_CATEGORIES else "Algemeen"})
        prev_tail = keys_this[-TAIL_SIZE:]

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    when = found_date or today
    expenses = [Expense(datum=when, item=r["name"], aantal=r["qty"], prijs=r["price"],
                        categorie=r["cat"], naam="") for r in rows]

    def close(a: float, b: float) -> bool:
        return abs(a - b) <= 0.05

    items_sum = sum(e.prijs for e in expenses)
    leeggoed = totals["leeggoed_totaal"]
    btw = totals["btw_totaal"]
    goederen = totals["totaal_goederen"]
    te_betalen = totals["totaal_te_betalen"]

    if goederen and not close(items_sum, goederen):
        LAST_WARNING = (f"Som van de items ({format_money(items_sum)}) wijkt af van 'totaal goederen' "
                        f"op het ticket ({format_money(goederen)}). Controleer de rijen.")

    if leeggoed:
        expenses.append(Expense(datum=when, item="Leeggoed", aantal="1", prijs=leeggoed, categorie="Alcohol"))

    if btw:
        base = goederen or items_sum
        add_btw = True
        if te_betalen:
            incl = close(base + leeggoed, te_betalen)         # BTW zit al in de prijzen
            excl = close(base + leeggoed + btw, te_betalen)   # BTW komt er nog bovenop
            add_btw = not (incl and not excl)
        if add_btw:
            expenses.append(Expense(datum=when, item="BTW", aantal="1", prijs=btw, categorie="Algemeen"))
    return expenses
