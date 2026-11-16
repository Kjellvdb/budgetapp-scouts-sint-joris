from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app import session_store, storage
from app.templates import templates

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
class RestUpdate(BaseModel):
    naam: str
    value: bool

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/overzicht", tags=["overzicht"])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def summary_view(request: Request):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    try:
        storage.save_summary_to_excel()
        summary, person_rows = storage.get_summary()
        error = None
    except Exception as e:
        summary = storage.Summary()
        person_rows = []
        error = str(e)
    total_alcohol_drinkers = sum(1 for person in person_rows if person.alcohol_aandeel > 0)
    total_sterke_drinkers = sum(1 for person in person_rows if person.sterke_aandeel > 0)
    drink_parts = []
    if summary.alcohol:
        drink_parts.append(f"alcohol ÷ {total_alcohol_drinkers} drinkers")
    if summary.sterke_drank:
        drink_parts.append(f"sterke drank ÷ {total_sterke_drinkers} drinkers")
    drink_info = ", ".join(drink_parts) if drink_parts else ""
    return templates.TemplateResponse(
        request=request,
        name="summary.html",
        context={
            "summary": summary,
            "person_rows": person_rows,
            "drink_info": drink_info,
            "error": error,
            "filename": session_store.get_filename()
        },
    )

@router.post("/update-rest")
async def update_rest_betaald(data: RestUpdate):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    try:
        storage.set_rest_betaald(data.naam, data.value)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grafieken", response_class=HTMLResponse)
async def summary_charts_view(request: Request):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    try:
        summary, _ = storage.get_summary()
        expenses = storage.get_expenses()
        error = None
    except Exception as e:
        summary = storage.Summary()
        expenses = []
        error = str(e)
    valid_dates = [expense.get("Datum") for expense in expenses if expense.get("Datum")]
    earliest_date = min(valid_dates) if valid_dates else ""
    return templates.TemplateResponse(
        request=request,
        name="summary_charts.html",
        context={
            "summary": summary,
            "expenses": expenses,
            "earliest_date": earliest_date,
            "filename": session_store.get_filename(),
            "error": error
        },
    )
