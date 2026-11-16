from fastapi import APIRouter, Request, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

from app import session_store, storage
from app.templates import templates

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/budget", tags=["budget"])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/new", response_class=HTMLResponse)
async def new_budget_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="new_budget.html",
        context={},
    )

@router.post("/new")
async def create_new_budget(budget_name: str = Form(...), members_file: UploadFile = File(...)):
    try:
        safe_name = "".join(
            char for char in budget_name if char.isalnum() or char in (" ", "_", "-")
        ).strip() or "budget"
        filename = f"{safe_name}.xlsx"
        csv_data = await members_file.read()
        excel_bytes = storage.create_new_budget(budget_name, csv_data)
        session_store.load_from_bytes(excel_bytes, filename)
        return RedirectResponse(url="/leden", status_code=303)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fout bij aanmaken budget: {exc}")
