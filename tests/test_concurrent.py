
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import re

from app.main import app
from app import session_store, storage

def create_test_budget(user_number: int) -> bytes:
    """Maak een uniek Excel-budget voor elke gebruiker met een unieke naam en takken."""
    csv_data = (
        "Voornaam;Achternaam;Takken\n"
        f"Gebruiker{user_number};Test;Leiding\n"
    ).encode("utf-8")

    return storage.create_new_budget(
        f"Budget gebruiker {user_number}",
        csv_data,
    )

def simulate_user(user_number: int) -> dict:
    """Simuleer een gebruiker die een budget uploadt, ledenkosten bijwerkt, bezoekers en uitgaven toevoegt, en het budget downloadt."""
    username = f"Gebruiker{user_number}"
    visitor_name = f"Bezoeker{user_number}"
    expense_name = f"Uitgave{user_number}"
    filename = f"budget_user_{user_number}.xlsx"

    with TestClient(app) as client:
        home_response = client.get("/")
        assert home_response.status_code == 200
        session_id = client.cookies.get(
            session_store.SESSION_COOKIE_NAME
        )
        assert session_id is not None

        excel_bytes = create_test_budget(user_number)
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    BytesIO(excel_bytes),
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet",
                )
            },
            follow_redirects=False,
        )
        assert upload_response.status_code == 303

        cost_response = client.post(
            "/leden/update-all-cost",
            json={"cost": float(user_number * 10)},
        )
        assert cost_response.status_code == 200

        visitor_response = client.post(
            "/fourage/add",
            data={
                "naam": visitor_name,
                "kostprijs": float(user_number * 5),
                "betaald": "Nee",
                "alcohol": "Nee",
                "sterke": "Nee",
            },
            follow_redirects=False,
        )
        assert visitor_response.status_code == 303

        expense_response = client.post(
            "/uitgaven/add",
            data={
                "datum": "16/11/2026",
                "item": expense_name,
                "aantal": 1,
                "prijs": float(user_number * 3),
                "categorie": "Algemeen",
            },
            follow_redirects=False,
        )
        assert expense_response.status_code == 303

        members_response = client.get("/leden/")
        assert members_response.status_code == 200
        assert contains_exact_text(members_response.text, username)
        for other_user in range(1, 11):
            if other_user != user_number:
                assert not contains_exact_text(members_response.text, f"Gebruiker{other_user}"), f"User {user_number} can see user {other_user}"
        visitors_response = client.get("/fourage/")
        assert visitors_response.status_code == 200
        assert contains_exact_text(visitors_response.text, visitor_name)
        for other_user in range(1, 11):
            if other_user != user_number:
                assert not contains_exact_text(visitors_response.text, f"Bezoeker{other_user}"), f"User {user_number} can see visitor {other_user}"

        expenses_response = client.get("/uitgaven/")
        assert expenses_response.status_code == 200
        assert contains_exact_text(expenses_response.text, expense_name)
        for other_user in range(1, 11):
            if other_user != user_number:
                assert not contains_exact_text(expenses_response.text, f"Uitgave{other_user}"), f"User {user_number} can see expense {other_user}"

        download_response = client.get("/download")
        assert download_response.status_code == 200
        assert (
            f"filename={filename}"
            in download_response.headers["content-disposition"]
        )

        workbook = load_workbook(
            BytesIO(download_response.content),
            read_only=True,
            data_only=True,
        )
        assert storage.SHEET_MEMBERS in workbook.sheetnames
        assert storage.SHEET_VISITORS in workbook.sheetnames
        assert storage.SHEET_EXPENSES in workbook.sheetnames
        members_sheet = workbook[storage.SHEET_MEMBERS]
        visitors_sheet = workbook[storage.SHEET_VISITORS]
        expenses_sheet = workbook[storage.SHEET_EXPENSES]
        assert members_sheet["A2"].value == f"{username} Test"
        assert visitors_sheet["A2"].value == visitor_name
        assert expenses_sheet["B2"].value == expense_name
        assert members_sheet["C2"].value == float(user_number * 10)
        workbook.close()

        return {
            "user": username,
            "session_id": session_id,
            "filename": filename,
            "visitor": visitor_name,
            "expense": expense_name,
            "status": "success",
        }

def contains_exact_text(html: str, value: str) -> bool:
    """Controleer of de opgegeven waarde exact voorkomt in de HTML, zonder dat het deel uitmaakt van een ander woord."""
    pattern = rf"(?<!\w){re.escape(value)}(?!\w)"
    return re.search(pattern, html) is not None

def test_ten_users_can_work_concurrently():
    """Simuleer 10 gebruikers die gelijktijdig hun budget uploaden, ledenkosten bijwerken, bezoekers en uitgaven toevoegen, en het budget downloaden. Controleer dat elke gebruiker een unieke sessie heeft en dat hun gegevens onafhankelijk blijven."""
    results = []
    with ThreadPoolExecutor(
        max_workers=10
    ) as executor:
        futures = {
            executor.submit(simulate_user, user_number): user_number
            for user_number in range(1, 11)
        }
        for future in as_completed(futures):
            user_number = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exception:
                raise AssertionError(
                    f"Concurrent test failed for user {user_number}: {exception}"
                ) from exception

    assert len(results) == 10
    assert all(
        result["status"] == "success"
        for result in results
    )

    session_ids = [
        result["session_id"]
        for result in results
    ]
    assert len(set(session_ids)) == 10

    filenames = [
        result["filename"]
        for result in results
    ]
    assert len(set(filenames)) == 10

    assert len({
        result["visitor"]
        for result in results
    }) == 10
    assert len({
        result["expense"]
        for result in results
    }) == 10
