from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import date as date_type

from app import session_store, storage
from app.templates import templates

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
class ExpenseCreate(BaseModel):
    datum: str
    item: str
    aantal: int = 1
    prijs: float
    categorie: str = "Algemeen"
    persoon: Optional[str] = ""
    betaald: Optional[str] = "Nee"

class AddExpensesRequest(BaseModel):
    rows: List[ExpenseCreate]

class ExpenseUpdate(BaseModel):
    row: int
    field: str
    value: str | float

class DeleteExpensesRequest(BaseModel):
    rows: List[int]

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def parse_expense_date(datum: str):
    try:
        if "/" in datum:
            parts = datum.split("/")
            if len(parts) != 3:
                raise ValueError
            return date_type(int(parts[2]), int(parts[1]), int(parts[0]))
        if "-" in datum:
            parts = datum.split("-")
            if len(parts) != 3:
                raise ValueError
            if len(parts[0]) == 4:
                return date_type(int(parts[0]), int(parts[1]), int(parts[2]))
            return date_type(int(parts[2]), int(parts[1]), int(parts[0]))
        raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Ongeldig datumformaat.")


def validate_expense_person(categorie: str, persoon: Optional[str]) -> None:
    if categorie != "Persoonlijk" and persoon and persoon.strip():
        raise HTTPException(status_code=400, detail=("Persoon kan enkel ingevuld worden bij categorie 'Persoonlijk'."))
    if categorie == "Persoonlijk" and persoon and persoon.strip():
        members = [member["Naam"].lower() for member in storage.get_members()]
        visitors = [visitor["Naam"].lower() for visitor in storage.get_visitors()]
        if persoon.strip().lower() not in members + visitors:
            raise HTTPException(status_code=400, detail=("Opgegeven persoon bestaat niet in de leden- of bezoekerslijst."))

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/uitgaven", tags=["uitgaven"])

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
async def expenses_view(request: Request):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    try:
        rows = storage.get_expenses()
        error = None
    except KeyError as e:
        rows, error = [], str(e)
    members = storage.get_members()
    valid_leaders = []
    for member in members:
        naam = member.get("Naam")
        tak = str(member.get("Tak", "")).lower()
        if naam and "leiding" in tak:
            valid_leaders.append(naam)
    visitors = [visitor["Naam"] for visitor in storage.get_visitors() if visitor.get("Naam")]
    person_options = sorted(list(set(visitors + valid_leaders)))
    total_expenses = sum(float(expense.get("Prijs") or 0) for expense in rows)
    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "rows": rows, 
            "error": error, 
            "filename": session_store.get_filename(),
            "person_options": person_options,
            "total_expenses": total_expenses
        },
    )

@router.post("/add")
async def add_expense(
    datum: str = Form(...),
    item: str = Form(...),
    aantal: int = Form(1),
    prijs: float = Form(...),
    categorie: str = Form("Algemeen"),
    persoon: Optional[str] = Form(""),
    betaald: Optional[str] = Form("Nee"),
):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    validate_expense_person(categorie, persoon)
    parsed_datum = parse_expense_date(datum)
    storage.add_expense([parsed_datum, item, aantal, prijs, categorie, persoon or "", betaald or "Nee"])
    return RedirectResponse(url="/uitgaven/", status_code=303)

@router.post("/add-all")
async def add_all_expenses(data: AddExpensesRequest):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    if not data.rows:
        raise HTTPException(status_code=400, detail="Geen uitgaven geselecteerd.")
    validated_rows = []
    for expense in data.rows:
        validate_expense_person(expense.categorie, expense.persoon)
        parsed_date = parse_expense_date(expense.datum)
        validated_rows.append([
            parsed_date,
            expense.item,
            expense.aantal,
            expense.prijs,
            expense.categorie,
            expense.persoon or "",
            expense.betaald or "Nee",
        ])
    storage.add_expenses_bulk(validated_rows)
    return {"status": "success", "added": len(validated_rows)}

@router.post("/update")
async def update_expense_field(data: ExpenseUpdate):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Geen sessie actief.")
    valid_fields = ["datum", "item", "aantal", "prijs", "categorie", "persoon", "betaald"]
    if data.field not in valid_fields:
        raise HTTPException(status_code=400, detail="Ongeldig veld.")
    storage.update_expense(data.row, data.field, data.value)
    if data.field == "categorie" and data.value != "Persoonlijk":
        storage.update_expense(data.row, "persoon", "")
        storage.update_expense(data.row, "betaald", "Nee")
    return {"status": "success"}

@router.post("/delete")
async def delete_expenses(data: DeleteExpensesRequest):
    if not session_store.is_loaded():
        raise HTTPException(status_code=400, detail="Upload eerst een Excel-bestand.")
    storage.delete_expenses(data.rows)
    return {"status": "success"}
