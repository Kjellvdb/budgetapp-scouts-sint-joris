from typing import Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app import session_store, storage
from app.templates import templates

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
class MemberUpdate(BaseModel):
    row: int
    field: str
    value: Any

class GlobalCostUpdate(BaseModel):
    cost: float

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/leden", tags=["leden"])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def members_view(request: Request):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand of maak een nieuw budget aan.")
    try:
        rows = storage.get_members()
        error = None
    except KeyError as e:
        rows, error = [], str(e)
    total_income = sum(float(member.get("Kostprijs") or 0) for member in rows)
    return templates.TemplateResponse(
        request=request,
        name="members.html",
        context={
            "rows": rows,
            "error": error,
            "filename": session_store.get_filename(),
            "total_income": total_income
        },
    )

@router.post("/update")
async def update_member_field(data: MemberUpdate):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    col_mapping = {"kost": 3, "betaald": 4, "alcohol": 5, "sterke": 6}
    if data.field not in col_mapping:
        raise HTTPException(status_code=400, detail="Ongeldig veld.")
    col_idx = col_mapping.get(data.field)
    if not col_idx:
        raise HTTPException(status_code=400, detail="Ongeldig veld.")
    if data.field in ("alcohol", "sterke"):
        members = storage.get_members()
        member = next((member for member in members if member["_excel_row"] == data.row), None)
        if not member:
            raise HTTPException(status_code=400, detail="Lid niet gevonden.")
        is_leiding = "Leiding" in str(member.get("Tak", ""))
        if not is_leiding:
            raise HTTPException(status_code=400, detail="Enkel leiding kan alcohol en sterke drank consumeren/aanpassen.")
    storage.update_cell(storage.SHEET_MEMBERS, data.row, col_idx, data.value)
    return {"status": "success"}

@router.post("/update-all-cost")
async def update_all_member_cost(data: GlobalCostUpdate):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    try:
        cost_value = float(data.cost)
        if cost_value < 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Ongeldige kostprijs.")
    members = storage.get_members()
    sheet = storage.get_sheet(storage.SHEET_MEMBERS)
    for index, _ in enumerate(members):
        excel_row = index + 2
        sheet.cell(row=excel_row, column=3, value=data.cost)
    session_store.save_current()
    return {"status": "success"}
