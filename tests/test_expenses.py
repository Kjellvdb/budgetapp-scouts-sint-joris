from app import session_store, storage

def test_expenses_render(client):
    """Controleer of de uitgavenpagina correct laadt wanneer er een actieve sessie is."""
    response = client.get("/uitgaven/")
    assert response.status_code == 200
    assert "Uitgaven" in response.text

def test_expenses_without_session_returns_400(client):
    """Controleer dat uitgaven-routes zonder actieve sessie netjes een 400 fout geven."""
    session_store.clear()
    assert client.get("/uitgaven/").status_code == 400
    assert client.post("/uitgaven/add", data={"datum": "2026-07-01", "item": "Test", "aantal": 1, "prijs": 10.0, "categorie": "Algemeen"}).status_code == 400
    assert client.post("/uitgaven/update", json={"row": 2, "field": "prijs", "value": 15.0}).status_code == 400
    assert client.post("/uitgaven/delete", json={"rows": [2]}).status_code == 400

def test_add_expense(client):
    """Test het toevoegen van een nieuwe uitgave via de uitgaven-route."""
    initial_count = len(storage.get_expenses())
    response = client.post(
        "/uitgaven/add",
        data={
            "datum": "10/07/2026",
            "item": "Bakken Jupiler",
            "aantal": 4,
            "prijs": 64.00,
            "categorie": "Alcohol",
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    expenses = storage.get_expenses()
    assert len(expenses) == initial_count + 1

    added_expense = expenses[-1]
    assert added_expense["Item"] == "Bakken Jupiler"
    assert added_expense["Aantal"] == 4
    assert added_expense["Prijs"] == 64.00
    assert added_expense["Categorie"] == "Alcohol"
    assert added_expense["Persoon"] == ""
    assert added_expense["Betaald?"] == "Nee"

def test_add_expense_persoonlijk(client):
    """Test het toevoegen van een persoonlijke uitgave met een specifieke persoon."""
    initial_count = len(storage.get_expenses())
    response = client.post(
        "/uitgaven/add",
        data={
            "datum": "10/07/2026",
            "item": "Persoonlijke Uitgave",
            "aantal": 1,
            "prijs": 20.00,
            "categorie": "Persoonlijk",
            "persoon": "Liam Janssen",
            "betaald": "Ja"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    expenses = storage.get_expenses()
    assert len(expenses) == initial_count + 1

    added_expense = expenses[-1]
    assert added_expense["Item"] == "Persoonlijke Uitgave"
    assert added_expense["Aantal"] == 1
    assert added_expense["Prijs"] == 20.00
    assert added_expense["Categorie"] == "Persoonlijk"
    assert added_expense["Persoon"] == "Liam Janssen"
    assert added_expense["Betaald?"] == "Ja"

def test_add_expense_persoonlijk_nonexistent_person(client):
    """Test het toevoegen van een persoonlijke uitgave met een niet-bestaande persoon, wat een 400 fout zou moeten opleveren."""
    assert client.post(
        "/uitgaven/add",
        data={
            "datum": "10/07/2026",
            "item": "Persoonlijke Uitgave",
            "aantal": 1,
            "prijs": 20.00,
            "categorie": "Persoonlijk",
            "persoon": "Niet Bestaande Persoon",
            "betaald": "Ja"
        },
        follow_redirects=False
    ).status_code == 400

def test_add_expense_not_persoonlijk_with_person_and_betaald(client):
    """Test het toevoegen van een niet-persoonlijke uitgave met opgegeven persoon en betaald status, wat een 400 fout zou moeten opleveren."""
    assert client.post(
        "/uitgaven/add",
        data={
            "datum": "10/07/2026",
            "item": "Algemene Uitgave",
            "aantal": 1,
            "prijs": 20.00,
            "categorie": "Algemeen",
            "persoon": "Liam Janssen",
            "betaald": "Ja"
        },
        follow_redirects=False
    ).status_code == 400

def test_add_expense_other_date_format(client):
    """Test het toevoegen van een uitgave met een ander datumformaat (DD/MM/YYYY)."""
    initial_count = len(storage.get_expenses())
    response = client.post(
        "/uitgaven/add",
        data={
            "datum": "15/07/2026",
            "item": "Andere Datum Formaat",
            "aantal": 2,
            "prijs": 30.00,
            "categorie": "Algemeen",
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    expenses = storage.get_expenses()
    assert len(expenses) == initial_count + 1

    added_expense = expenses[-1]
    assert added_expense["Item"] == "Andere Datum Formaat"
    assert added_expense["Aantal"] == 2
    assert added_expense["Prijs"] == 30.00
    assert added_expense["Categorie"] == "Algemeen"
    assert added_expense["Datum"] == "2026-07-15"

def test_add_expense_invalid_date_format(client):
    """Test het toevoegen van een uitgave met een onjuist datumformaat, wat een 400 fout zou moeten opleveren."""
    assert client.post(
        "/uitgaven/add",
        data={
            "datum": "ongeldige datum",
            "item": "Boodschappen",
            "aantal": 1,
            "prijs": 20.00,
            "categorie": "Algemeen"
        },
        follow_redirects=False
    ).status_code == 400

def test_add_all_expenses(client):
    """Test het toevoegen van meerdere uitgaven in bulk via de add-all route."""
    initial_count = len(storage.get_expenses())
    rows = [
        {
            "datum": "2026-07-15",
            "item": f"Ticket item {index}",
            "aantal": index,
            "prijs": float(index * 2),
            "categorie": "Algemeen",
            "persoon": "",
            "betaald": "Nee",
        }
        for index in range(1, 21)
    ]

    response = client.post(
        "/uitgaven/add-all",
        json={"rows": rows},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "added": 20,
    }

    expenses = storage.get_expenses()
    assert len(expenses) == initial_count + 20

    added_items = {
        expense["Item"]: expense
        for expense in expenses
        if expense["Item"].startswith("Ticket item ")
    }
    assert len(added_items) == 20

    for index in range(1, 21):
        expense = added_items[f"Ticket item {index}"]
        assert expense["Aantal"] == index
        assert expense["Prijs"] == float(index * 2)
        assert expense["Categorie"] == "Algemeen"
        assert expense["Persoon"] == ""
        assert expense["Betaald?"] == "Nee"
        assert expense["Datum"] == "2026-07-15"

def test_add_all_expenses_invalid_row_does_not_add_anything(client):
    """Test dat het toevoegen van meerdere uitgaven in bulk met een ongeldige rij geen enkele uitgave toevoegt en een 400 fout oplevert."""
    initial_count = len(storage.get_expenses())
    rows = [
        {
            "datum": "2026-07-15",
            "item": "Valid ticket item",
            "aantal": 1,
            "prijs": 10.0,
            "categorie": "Algemeen",
        },
        {
            "datum": "invalid-date",
            "item": "Invalid ticket item",
            "aantal": 1,
            "prijs": 20.0,
            "categorie": "Algemeen",
        },
    ]

    response = client.post(
        "/uitgaven/add-all",
        json={"rows": rows},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Ongeldig datumformaat."
    assert len(storage.get_expenses()) == initial_count

def test_update_expense_field(client):
    """Test het bijwerken van specifieke velden van een individuele uitgave."""
    client.post(
        "/uitgaven/add",
        data={"datum": "11/07/2026", "item": "Boodschappen", "aantal": 1, "prijs": 100.0, "categorie": "Algemeen"}
    )
    expenses = storage.get_expenses()
    target_expense = expenses[-1]
    target_row = target_expense["_excel_row"]

    assert client.post("/uitgaven/update", json={"row": target_row, "field": "aantal", "value": 2.0}).status_code == 200
    assert client.post("/uitgaven/update", json={"row": target_row, "field": "prijs", "value": 120.50}).status_code == 200
    assert client.post("/uitgaven/update", json={"row": target_row, "field": "item", "value": "Grote Boodschappen"}).status_code == 200

    updated_expenses = storage.get_expenses()
    updated = next(expense for expense in updated_expenses if expense["_excel_row"] == target_row)
    assert updated["Item"] == "Grote Boodschappen"
    assert updated["Aantal"] == 2
    assert updated["Prijs"] == 120.50

def test_update_expense_algemeen_to_persoonlijk(client):
    """Test het bijwerken van een uitgave van Algemeen naar Persoonlijk met een geldige persoon."""
    client.post(
        "/uitgaven/add",
        data={"datum": "12/07/2026", "item": "Algemene Uitgave", "aantal": 1, "prijs": 50.0, "categorie": "Algemeen"}
    )
    expenses = storage.get_expenses()
    target_expense = expenses[-1]
    target_row = target_expense["_excel_row"]

    client.post("/uitgaven/update", json={"row": target_row, "field": "categorie", "value": "Persoonlijk"})
    client.post("/uitgaven/update", json={"row": target_row, "field": "persoon", "value": "Liam Janssen"})

    updated_expenses = storage.get_expenses()
    updated = next(expense for expense in updated_expenses if expense["_excel_row"] == target_row)
    assert updated["Categorie"] == "Persoonlijk"
    assert updated["Persoon"] == "Liam Janssen"
    assert updated["Betaald?"] == "Nee"

def test_update_expense_persoonlijk_to_algemeen(client):
    """Test het bijwerken van een uitgave van Persoonlijk naar Algemeen, waarbij persoon en betaald status worden verwijderd."""
    client.post(
        "/uitgaven/add",
        data={"datum": "13/07/2026", "item": "Persoonlijke Uitgave", "aantal": 1, "prijs": 30.0, "categorie": "Persoonlijk", "persoon": "Liam Janssen", "betaald": "Ja"}
    )
    expenses = storage.get_expenses()
    target_expense = expenses[-1]
    target_row = target_expense["_excel_row"]

    client.post("/uitgaven/update", json={"row": target_row, "field": "categorie", "value": "Algemeen"})

    updated_expenses = storage.get_expenses()
    updated = next(expense for expense in updated_expenses if expense["_excel_row"] == target_row)
    assert updated["Categorie"] == "Algemeen"
    assert updated["Persoon"] == ""
    assert updated["Betaald?"] == "Nee"

def test_update_expense_field_invalid_field(client):
    """Controleer dat het bewerken van een onbestaand veld netjes een 400 fout oplevert."""
    client.post(
        "/uitgaven/add",
        data={"datum": "14/07/2026", "item": "Test Uitgave", "aantal": 1, "prijs": 40.0, "categorie": "Algemeen"}
    )
    expenses = storage.get_expenses()
    target_expense = expenses[-1]
    target_row = target_expense["_excel_row"]

    assert client.post("/uitgaven/update", json={"row": target_row, "field": "onbestaand_veld", "value": "test"}).status_code == 400

def test_delete_expenses(client):
    """Test het selectief verwijderen van een of meerdere uitgaven."""
    client.post(
        "/uitgaven/add",
        data={"datum": "12/07/2026", "item": "Te Verwijderen Item", "aantal": 1, "prijs": 15.0, "categorie": "Algemeen"}
    )
    expenses = storage.get_expenses()
    target_row = expenses[-1]["_excel_row"]

    delete_response = client.post("/uitgaven/delete", json={"rows": [target_row]})
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "success"}

    remaining_expenses = storage.get_expenses()
    assert not any(e["_excel_row"] == target_row for e in remaining_expenses)
