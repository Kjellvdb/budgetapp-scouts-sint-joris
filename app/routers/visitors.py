from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List

from app import session_store, storage
from app.templates import templates

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
class VisitorUpdate(BaseModel):
    row: int
    field: str
    value: str | float

class DeleteVisitorsRequest(BaseModel):
    rows: List[int]

class GlobalCostUpdate(BaseModel):
    cost: float

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/fourage", tags=["fourage"])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def visitors_view(request: Request):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand of maak een nieuw budget aan.")
    try:
        rows = storage.get_visitors()
        error = None
    except KeyError as e:
        rows, error = [], str(e)
    total_income = sum(float(visitor.get("Kostprijs") or 0) for visitor in rows)
    return templates.TemplateResponse(
        request=request,
        name="visitors.html",
        context={
            "rows": rows,
            "error": error,
            "filename": session_store.get_filename(),
            "total_income": total_income
        },
    )

@router.post("/add")
async def add_visitor(
    naam: str = Form(...),
    kostprijs: float = Form(0.0),
    betaald: str = Form("Nee"),
    alcohol: str = Form("Nee"),
    sterke: str = Form("Nee"),
):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    storage.add_visitor([naam, kostprijs, betaald, alcohol, sterke])
    return RedirectResponse(url="/fourage/", status_code=303)

@router.post("/update")
async def update_visitor_field(data: VisitorUpdate):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    col_mapping = {"naam": 1, "kost": 2, "betaald": 3, "alcohol": 4, "sterke": 5}
    if data.field not in col_mapping:
        raise HTTPException(status_code=400, detail="Ongeldig veld.")
    storage.update_visitor(data.row, data.field, data.value)
    return {"status": "success"}

@router.post("/delete")
async def delete_visitors(data: DeleteVisitorsRequest):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    storage.delete_visitors(data.rows)
    return {"status": "success"}

@router.post("/update-all-cost")
async def update_all_visitor_cost(data: GlobalCostUpdate):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    try:
        cost_value = float(data.cost)
        if cost_value < 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Ongeldige kostprijs.")
    sheet = storage.get_sheet(storage.SHEET_VISITORS)
    for row in range(2, sheet.max_row + 1):
        sheet.cell(row=row, column=2, value=data.cost)
    session_store.save_current()
    return {"status": "success"}
