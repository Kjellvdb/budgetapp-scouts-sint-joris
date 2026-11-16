from datetime import datetime, timedelta, timezone
from uuid import uuid4
from openpyxl import Workbook

import pytest
import io
import json

from app import session_store

def create_test_workbook() -> bytes:
    """Maak een minimaal geldig Excel-bestand."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "Testbudget"
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

@pytest.fixture
def ttl_session(tmp_path, monkeypatch):
    """Maak een geïsoleerde sessie aan met een korte TTL."""
    monkeypatch.setattr(session_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        session_store,
        "SESSION_TTL",
        timedelta(seconds=10),
    )
    session_id = str(uuid4())
    token = session_store.set_session_id(session_id)

    try:
        session_store.touch_current_session()
        session_store.load_from_bytes(create_test_workbook(), "test.xlsx")
        yield session_id, tmp_path
    finally:
        session_store.reset_session_id(token)

def set_last_activity(session_dir, seconds_ago):
    """Wijzig de laatste activiteit in de sessiemetadata."""
    metadata_path = session_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    last_activity = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    metadata["last_activity"] = last_activity.isoformat()
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

def test_session_remains_available_within_ttl(ttl_session):
    """Test dat een sessie beschikbaar blijft zolang deze binnen de TTL valt."""
    session_id, data_dir = ttl_session
    session_dir = data_dir / session_id
    set_last_activity(session_dir, seconds_ago=5)

    deleted = session_store.cleanup_expired_sessions()
    assert deleted == 0
    assert session_dir.exists()

    token = session_store.set_session_id(session_id)
    try:
        workbook = session_store.get_workbook()
        assert workbook.active["A1"].value == "Testbudget"
        assert session_store.get_filename() == "test.xlsx"
    finally:
        session_store.reset_session_id(token)

def test_session_expires_after_ttl(ttl_session):
    """Test dat een sessie wordt verwijderd nadat de TTL is overschreden."""
    session_id, data_dir = ttl_session
    session_dir = data_dir / session_id
    set_last_activity(session_dir, seconds_ago=15)

    deleted = session_store.cleanup_expired_sessions()
    assert deleted == 1
    assert not session_dir.exists()

    token = session_store.set_session_id(session_id)
    try:
        assert not session_store.is_loaded()
        with pytest.raises(RuntimeError, match="Geen bestand geladen"):
            session_store.get_workbook()
    finally:
        session_store.reset_session_id(token)
