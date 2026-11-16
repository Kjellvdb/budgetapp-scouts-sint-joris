from __future__ import annotations
from pathlib import Path
from typing import Optional
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime, timedelta, timezone

import io
import threading
import shutil
import json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_FILENAME = "budget.xlsx"
SESSION_COOKIE_NAME = "budget_session_id"
SESSION_TTL = timedelta(days=30)
METADATA_FILENAME = "metadata.json"

_sessions: dict[str, SessionState] = {}
_registry_lock = threading.RLock()
_metadata_lock = threading.Lock()
_current_session_id: ContextVar[Optional[str]] = ContextVar(
    SESSION_COOKIE_NAME,
    default=None,
)

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
@dataclass
class SessionState:
    workbook: Optional[Workbook] = None
    filename: str = DEFAULT_FILENAME
    lock: threading.RLock = field(default_factory=threading.RLock)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def validate_session_id(session_id: str) -> str:
    try:
        return str(UUID(str(session_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Ongeldig sessie-ID.")

def set_session_id(session_id: str) -> Token:
    normalized_id = validate_session_id(session_id)
    return _current_session_id.set(normalized_id)

def reset_session_id(token: Token) -> None:
    _current_session_id.reset(token)

def get_session_id() -> str:
    session_id = _current_session_id.get()
    if not session_id:
        raise RuntimeError("Geen actieve gebruikerssessie.")
    return session_id

def touch_current_session() -> None:
    session_id = get_session_id()
    directory = _session_directory(session_id)
    metadata_path = directory / METADATA_FILENAME
    temporary_path = metadata_path.with_suffix(".tmp")
    with _metadata_lock:
        with _registry_lock:
            directory.mkdir(parents=True, exist_ok=True)
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    raise RuntimeError(f"Metadata van sessie {session_id} is ongeldig.")
            else:
                now = datetime.now(timezone.utc).isoformat()
                metadata = {"session_id": session_id, "created_at": now}
            metadata["last_activity"] = datetime.now(timezone.utc).isoformat()
            temporary_path.write_text(json.dumps(metadata, indent=4), encoding="utf-8")
            temporary_path.replace(metadata_path)

def cleanup_expired_sessions() -> int:
    now = datetime.now(timezone.utc)
    deleted_count = 0
    with _registry_lock:
        for directory in DATA_DIR.iterdir():
            if not directory.is_dir():
                continue
            try:
                session_id = validate_session_id(directory.name)
            except ValueError:
                continue
            metadata_path = directory / METADATA_FILENAME
            if not metadata_path.is_file():
                continue
            try:
                metadata = json.loads(
                    metadata_path.read_text(encoding="utf-8")
                )
                last_activity = datetime.fromisoformat(
                    metadata["last_activity"]
                )
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(
                        tzinfo=timezone.utc
                    )
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                json.JSONDecodeError,
            ):
                continue
            if now - last_activity <= SESSION_TTL:
                continue
            state = _sessions.pop(session_id, None)
            shutil.rmtree(directory)
            if state is not None:
                state.workbook = None
                state.filename = DEFAULT_FILENAME
            deleted_count += 1
    return deleted_count


def _session_directory(session_id: str) -> Path:
    return DATA_DIR / validate_session_id(session_id)


def _get_state(create: bool = True) -> Optional[SessionState]:
    session_id = get_session_id()
    with _registry_lock:
        state = _sessions.get(session_id)
        if state is None and create:
            state = SessionState()
            _sessions[session_id] = state
        return state


def _get_paths() -> tuple[Path, Path]:
    directory = _session_directory(get_session_id())
    return (
        directory / DEFAULT_FILENAME,
        directory / "filename.txt",
    )


def _auto_save() -> None:
    state = _get_state(create=False)
    if state is None:
        return
    with state.lock:
        if state.workbook is None:
            return
        workbook_path, metadata_path = _get_paths()
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        state.workbook.save(workbook_path)
        metadata_path.write_text(
            state.filename,
            encoding="utf-8",
        )

def save_current() -> None:
    _auto_save()

def clear() -> None:
    session_id = get_session_id()
    with _registry_lock:
        state = _sessions.pop(session_id, None)
    if state is not None:
        with state.lock:
            state.workbook = None
            state.filename = DEFAULT_FILENAME
    directory = _session_directory(session_id)
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)


def load_from_bytes(data: bytes, filename: str) -> None:
    workbook = load_workbook(io.BytesIO(data))
    state = _get_state()
    with state.lock:
        state.workbook = workbook
        state.filename = filename
        _auto_save()

def get_workbook() -> Workbook:
    state = _get_state()
    with state.lock:
        if state.workbook is not None:
            return state.workbook
        workbook_path, metadata_path = _get_paths()
        if not workbook_path.exists():
            raise RuntimeError(
                "Geen bestand geladen. Upload eerst een Excel-bestand "
                "of maak een nieuw budget aan."
            )
        try:
            state.workbook = load_workbook(workbook_path)
            if metadata_path.exists():
                state.filename = metadata_path.read_text(
                    encoding="utf-8"
                ).strip() or DEFAULT_FILENAME
        except Exception as exc:
            state.workbook = None
            raise RuntimeError(
                f"Het budgetbestand kon niet worden geladen: {exc}"
            ) from exc
        return state.workbook

def get_filename() -> str:
    state = _get_state()
    with state.lock:
        if state.filename != DEFAULT_FILENAME:
            return state.filename
        _, metadata_path = _get_paths()
        if metadata_path.exists():
            state.filename = metadata_path.read_text(
                encoding="utf-8"
            ).strip() or DEFAULT_FILENAME
        return state.filename

def is_loaded() -> bool:
    state = _get_state()
    with state.lock:
        if state.workbook is not None:
            return True
        workbook_path, metadata_path = _get_paths()
        if not workbook_path.exists():
            return False
        try:
            state.workbook = load_workbook(workbook_path)
            if metadata_path.exists():
                state.filename = metadata_path.read_text(
                    encoding="utf-8"
                ).strip() or DEFAULT_FILENAME
            return True
        except Exception:
            state.workbook = None
            return False

def to_bytes() -> bytes:
    state = _get_state()
    with state.lock:
        workbook = get_workbook()
        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        return buffer.read()
