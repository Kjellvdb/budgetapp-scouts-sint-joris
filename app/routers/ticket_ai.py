from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps
from groq import Groq

import asyncio
import base64
import collections
import io
import json
import os
import queue
import re
import threading
import time

from app import session_store

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "qwen/qwen3.8-27b"
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGES = 10
STRIP_RATIO = 1.0
STRIP_OVERLAP = 0.12
TARGET_WIDTH = 1000
MAX_WIDTH = 1000
MAX_STRIPS = 30
TAIL_SIZE = 6
DEFAULT_SLOTS = 2

MAX_PARALLEL = 2
TOKENS_PER_MINUTE = 8000
LIMIT_SAFETY = 0.99
INITIAL_ESTIMATE = 2200
MAX_WAIT = 180
MAX_TOTAL_WAIT = 600

AI_CATEGORIES = ["Algemeen", "Alcohol", "Sterke drank"]

PROMPT = (
    "STROOK van een kassaticket/factuur (bv. Colruyt). Negeer regels die aan de boven- of onderrand afgesneden zijn.\n"
    "Per productregel (met artikelnummer): artikelnr (Art.Nr, cijfers), item, aantal (Hoev.), "
    "totale_prijs (kolom Bedrag, NIET eenheidsprijs), categorie ('Alcohol' bier/wijn, "
    "'Sterke drank' likeur/whisky/gin/vodka, anders 'Algemeen').\n"
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

_DATE_PARSE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y",
    "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
class _TokenLimiter:
    def __init__(self, per_minute: int):
        self.limit = per_minute
        self.lock = threading.Lock()
        self.events: collections.deque = collections.deque()
        self.blocked_until = 0.0
        self.estimate = INITIAL_ESTIMATE
        self._seen: list[int] = []

    def _used(self, now: float) -> int:
        while self.events and now - self.events[0][0] >= 60:
            self.events.popleft()
        return sum(e[1] for e in self.events)

    def acquire(self, on_wait=None, cancel: threading.Event | None = None) -> list:
        stop = cancel or threading.Event()
        while True:
            if stop.is_set():
                raise RuntimeError("Geannuleerd")
            with self.lock:
                now  = time.monotonic()
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
            if stop.wait(min(max(wait, 0.5), 3)):
                raise RuntimeError("Geannuleerd")

    def record(self, event: list, actual: int | None) -> None:
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

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def _parse_price(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    string_value = str(value).replace("€", "").replace(" ", "").strip()
    if not string_value:
        return None
    if "," in string_value and "." in string_value:
        if string_value.rfind(",") > string_value.rfind("."):
            string_value = string_value.replace(".", "").replace(",", ".")
        else:
            string_value = string_value.replace(",", "")
    else:
        string_value = string_value.replace(",", ".")
    try:
        return float(string_value)
    except ValueError:
        return None

def _format_quantity(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()

def _parse_date(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    text = str(value).strip()
    if not text:
        return None
    for format in _DATE_PARSE_FORMATS:
        try:
            return datetime.strptime(text, format).replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            continue
    return None

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
        fixed = re.sub(r'(:\s*)(-?\d+,\d+)(\s*[,}\]])', r'\1"\2"\3', text)
        return json.loads(fixed)

def _strip_parts(image_bytes: bytes) -> list[dict]:
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    width, height = image.size
    target = TARGET_WIDTH if width < TARGET_WIDTH else min(width, MAX_WIDTH)
    if target != width:
        image = image.resize((target, int(height * target / width)), Image.LANCZOS)
        width, height = image.size
    strip_height = int(width * STRIP_RATIO)
    step = int(strip_height * (1 - STRIP_OVERLAP))
    tops, top = [], 0
    while True:
        if top + strip_height >= height:
            tops.append(max(0, height - strip_height))
            break
        tops.append(top)
        top += step
    parts = []
    for top in tops:
        buf = io.BytesIO()
        image.crop((0, top, width, min(top + strip_height, height))).save(buf, "JPEG", quality=88)
        data = buf.getvalue()
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Een deel van de foto is te groot voor de AI. Verklein de foto.")
        b64 = base64.b64encode(data).decode("utf-8")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return parts

def _fmt_time(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}min {seconds % 60:02d}s"

def _retry_delay(exc: Exception) -> float | None:
    text = str(exc)
    if getattr(exc, "status_code", None) != 429 and "rate_limit" not in text.lower() and "429" not in text:
        return None
    seconds = 0.0
    message = re.search(r"try again in\s+([0-9hms.\s]+)", text)
    if message:
        for val, unit in re.findall(r"([\d.]+)\s*(ms|height|m|s)", message.group(1)):
            seconds += float(val) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    return seconds or 20.0

def _extract_expenses_from_bytes(
    images_bytes: list[bytes],
    progress=None,
) -> tuple[list[dict], str]:
    def note_finished() -> None:
        now = time.monotonic()
        finish_times.append(now)
        peak_slots[0] = max(peak_slots[0], sum(1 for time in list(finish_times) if now - time < 60))

    def eta_seconds() -> float:
        remaining = total - done[0]
        if remaining <= 0:
            return 0.0
        now = time.monotonic()
        window = collections.deque(time - now for time in sorted(finish_times) if now - time < 60)
        slots = max(peak_slots[0], len(window), 1)
        t_eta = 0.0
        for _ in range(remaining):
            while window and window[0] <= t_eta - 60:
                window.popleft()
            while len(window) >= slots:
                t_eta = max(t_eta, window[0] + 60)
                window.popleft()
            window.append(t_eta)
        return t_eta + 3

    def say(msg: str) -> None:
        if progress:
            progress(msg)

    def ask(content: list[dict], json_mode: bool):
        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "max_completion_tokens": 1200,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        while True:
            event = LIMITER.acquire(
                on_wait=lambda width: say(
                    f"⏸ Wachten op AI-limiet… Nog ± {_fmt_time(max(eta_seconds(), width))} "
                    f"({done[0]}/{total} klaar)"
                ),
            )
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as exc:
                LIMITER.record(event, 0)
                if "reasoning_effort" in kwargs and "reasoning_effort" in str(exc):
                    kwargs.pop("reasoning_effort")
                    continue
                wait = _retry_delay(exc)
                if wait is None:
                    transient = (
                        (getattr(exc, "status_code", None) or 0) >= 500
                        or "Connection" in type(exc).__name__
                        or "Timeout"    in type(exc).__name__
                    )
                    if transient and time.monotonic() < deadline:
                        time.sleep(2)
                        continue
                    raise
                if wait > MAX_WAIT or time.monotonic() + wait > deadline:
                    raise RuntimeError(
                        f"Groq-limiet bereikt - probeer opnieuw over ± {int(wait // 60) + 1} min."
                    ) from exc
                LIMITER.block(wait)
                continue
            usage = getattr(response, "usage", None)
            LIMITER.record(event, getattr(usage, "total_tokens", None))
            return response

    def fetch(args: tuple[int, dict]):
        index, part = args
        content = [
            {"type": "text", "text": PROMPT},
            {"type": "text", "text": f"Strook {index} van {total}:"},
            part,
        ]
        try:
            response = ask(content, json_mode=True)
        except Exception as exc:
            if "json_validate_failed" not in str(exc):
                raise
            response = ask(content, json_mode=False)
        done[0] += 1
        note_finished()
        remaining = total - done[0]
        say(
            "⏳ AI leest het ticket uit… "
            + (f"Nog ± {_fmt_time(eta_seconds())} " if remaining else "")
            + f"({done[0]}/{total} klaar)"
        )
        return _parse_json(response.choices[0].message.content or "")

    def _close(a: float, b: float) -> bool:
            return abs(a - b) <= 0.05

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise RuntimeError("Geen GROQ_API_KEY gevonden in de omgevingsvariabelen.")
    client = Groq(api_key=groq_key, max_retries=0, timeout=30)
    model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
    strips: list[dict] = []
    for img_bytes in images_bytes:
        strips.extend(_strip_parts(img_bytes))
    if len(strips) > MAX_STRIPS:
        raise RuntimeError(
            f"Het ticket levert {len(strips)} stroken op (max {MAX_STRIPS}). "
            "Gebruik minder of kleinere foto's."
        )
    total = len(strips)
    done = [0]
    deadline = time.monotonic() + MAX_TOTAL_WAIT
    finish_times: list[float] = []
    peak_slots = [DEFAULT_SLOTS]

    say(f"⏳ AI leest het ticket uit… (0/{total} klaar)")
    pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
    try:
        results = list(pool.map(fetch, enumerate(strips, start=1)))
    finally:
        pool.shutdown(wait=False)
    totals = {
        "leeggoed_totaal": 0.0, "btw_totaal": 0.0,
        "totaal_goederen": 0.0, "totaal_te_betalen": 0.0,
    }
    rows: list[dict] = []
    found_date: datetime | None = None
    prev_tail: list[tuple] = []
    for data in results:
        if isinstance(data, dict):
            message = re.search(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", str(data.get("datum") or ""))
            found_date = found_date or (
                _parse_date(message.group(0).replace(".", "/").replace("-", "/")) if message else None
            )
            for key in totals:
                value = _parse_price(data.get(key)) or 0.0
                if value and not totals[key]:
                    totals[key] = value
        items = data if isinstance(data, list) else data.get("items", [])
        tail = list(prev_tail)
        keys_this: list[tuple] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("item") or "").strip()
            if not name or name.lower() in ("leeggoed", "btw"):
                continue
            artikelnummer = re.sub(r"\D", "", str(item.get("artikelnr") or ""))
            price = _parse_price(item.get("totale_prijs")) or 0.0
            quantity = _format_quantity(item.get("aantal")) or "1"
            key = (artikelnummer or name.lower()[:12], quantity, round(price, 2))
            keys_this.append(key)
            if key in tail:
                tail.remove(key)
                continue
            categorie = item.get("categorie", "Algemeen")
            rows.append({
                "naam": name, "aantal": quantity, "prijs": price,
                "categorie": categorie if categorie in AI_CATEGORIES else "Algemeen",
            })
        prev_tail = keys_this[-TAIL_SIZE:]
    when = found_date or datetime.now()
    datum_iso = when.strftime("%Y-%m-%d")
    expenses: list[dict] = [
        {
            "datum": datum_iso, "item": row["naam"],
            "aantal": row["aantal"], "prijs": round(row["prijs"], 2),
            "categorie": row["categorie"],
        }
        for row in rows
    ]
    leeggoed = totals["leeggoed_totaal"]
    btw = totals["btw_totaal"]
    goederen = totals["totaal_goederen"]
    te_betalen = totals["totaal_te_betalen"]
    if leeggoed:
        expenses.append({
            "datum": datum_iso, "item": "Leeggoed",
            "aantal": "1", "prijs": round(leeggoed, 2), "categorie": "Alcohol",
        })
    if btw:
        base = goederen or sum(expense["prijs"] for expense in expenses)
        add_btw = True
        if te_betalen:
            incl = _close(base + leeggoed, te_betalen)
            excl = _close(base + leeggoed + btw, te_betalen)
            add_btw = not (incl and not excl)
        if add_btw:
            expenses.append({
                "datum": datum_iso, "item": "BTW",
                "aantal": "1", "prijs": round(btw, 2), "categorie": "Algemeen",
            })
    warning = ""
    items_sum = sum(expense["prijs"] for expense in expenses if expense["item"] not in ("BTW", "Leeggoed"))
    if goederen and not _close(items_sum, goederen):
        warning = (
            f"Som van de items (€ {items_sum:.2f}) wijkt af van 'totaal goederen' "
            f"op het ticket (€ {goederen:.2f}). Controleer de rijen."
        )
    return expenses, warning

def _sse(payload: dict) -> str:
    """Formatteer één SSE-frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/uitgaven", tags=["ticket-ai"])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/scan")
async def scan_ticket(files: list[UploadFile] = File(...)):
    def progress(msg: str) -> None:
        message_queue.put(msg)

    def worker():
        try:
            expenses, warning = _extract_expenses_from_bytes(images_bytes, progress=progress)
            result_holder.append((expenses, warning))
        except Exception as exc:
            result_holder.append(exc)
        finally:
            message_queue.put(None)

    async def event_stream():
            loop = asyncio.get_event_loop()
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            while True:
                try:
                    message = await loop.run_in_executor(None, lambda: message_queue.get(timeout=120))
                except Exception:
                    yield _sse({"error": "Time-out wachten op AI."})
                    return
    
                if message is None:
                    break
                yield _sse({"status": message})
            thread.join(timeout=5)
            if not result_holder:
                yield _sse({"error": "Geen resultaat ontvangen van de AI."})
                return
            result = result_holder[0]
            if isinstance(result, Exception):
                yield _sse({"error": str(result)})
            else:
                expenses, warning = result
                yield _sse({"done": True, "expenses": expenses, "warning": warning})

    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    if not files:
        raise HTTPException(status_code=422, detail="Geen bestanden ontvangen.")
    if len(files) > MAX_IMAGES:
        raise HTTPException(status_code=422, detail=f"Maximaal {MAX_IMAGES} foto's per scan.")
    images_bytes: list[bytes] = []
    for file in files:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=422, detail=f"Leeg bestand: {file.filename}")
        images_bytes.append(content)
    message_queue: queue.Queue[str | None] = queue.Queue()
    result_holder: list = []
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
