import io
import openpyxl
from app import session_store, storage

def test_download_without_session_returns_400(client):
    """Controleer dat downloaden zonder actieve sessie een 400 fout oplevert."""
    session_store.clear()
    response = client.get("/download")
    assert response.status_code == 400

def test_upload_invalid_file_extension(client):
    """Controleer dat het uploaden van een ongeldig bestandstype (geen .xlsx of .xlsm) een 400 fout oplevert."""
    bad_file = client.post(
        "/upload",
        files={"file": ("notities.txt", io.BytesIO(b"hallo tekst"), "text/plain")}
    )
    assert bad_file.status_code == 400

    bad_csv = client.post(
        "/upload",
        files={"file": ("leden.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")}
    )
    assert bad_csv.status_code == 400

def test_download_active_budget(client):
    """Test het downloaden van het actieve Excel-budgetbestand en controleer headers en bestandsnaam."""
    response = client.get("/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "filename=test.xlsx" in response.headers["content-disposition"]
    assert len(response.content) > 0

def test_upload_download_roundtrip_persistence(client):
    """Test de volledige cyclus: wijzig data, download het Excel-bestand, wis de sessie en upload het bestand opnieuw."""
    members = storage.get_members()
    assert len(members) > 0
    target_row = members[0]["_excel_row"]

    assert client.post("/leden/update", json={"row": target_row, "field": "kost", "value": 75.0}).status_code == 200
    assert client.post("/uitgaven/add", data={"datum": "2026-07-20", "item": "Kampmateriaal", "aantal": 2, "prijs": 150.0, "categorie": "Algemeen"}, follow_redirects=False).status_code == 303

    download_resp = client.get("/download")
    assert download_resp.status_code == 200
    downloaded_bytes = download_resp.content

    workbook_check = openpyxl.load_workbook(io.BytesIO(downloaded_bytes))
    assert storage.SHEET_MEMBERS in workbook_check.sheetnames
    assert storage.SHEET_EXPENSES in workbook_check.sheetnames

    session_store.clear()
    assert session_store.is_loaded() is False

    reupload_response = client.post(
        "/upload",
        files={"file": ("test_backup.xlsx", io.BytesIO(downloaded_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        follow_redirects=False
    )
    assert reupload_response.status_code == 303
    assert reupload_response.headers["location"] == "/uitgaven"

    assert session_store.is_loaded() is True
    assert session_store.get_filename() == "test_backup.xlsx"

    restored_members = storage.get_members()
    restored_target = next(member for member in restored_members if member["_excel_row"] == target_row)
    assert restored_target["Kostprijs"] == 75.0

    restored_expenses = storage.get_expenses()
    assert any(expense["Item"] == "Kampmateriaal" and expense["Prijs"] == 150.0 for expense in restored_expenses)
