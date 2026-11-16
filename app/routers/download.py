from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app import session_store

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/download")
async def download_file():
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen actief bestand om te downloaden.")
    file_bytes = session_store.to_bytes()
    filename = session_store.get_filename() or "budget.xlsx"
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
