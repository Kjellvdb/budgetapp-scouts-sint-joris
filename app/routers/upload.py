from fastapi import APIRouter, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app import session_store
from app.templates import templates

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "loaded": session_store.is_loaded(),
            "filename": session_store.get_filename() if session_store.is_loaded() else None,
        },
    )

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Alleen .xlsx of .xlsm bestanden zijn toegestaan.")
    contents = await file.read()
    try:
        session_store.load_from_bytes(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Kon bestand niet inlezen: {e}")
    return RedirectResponse(url="/uitgaven", status_code=303)
