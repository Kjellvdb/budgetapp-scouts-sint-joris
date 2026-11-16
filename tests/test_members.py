from app import session_store, storage

def test_members_render(client):
    """Controleer of de ledenpagina correct laadt wanneer er een actieve sessie is."""
    response = client.get("/leden/")
    assert response.status_code == 200
    assert "Ledenlijst" in response.text

def test_members_without_session_returns_400(client):
    """Controleer dat routes zonder actieve sessie netjes een 400 fout geven."""
    session_store.clear()
    assert client.get("/leden/").status_code == 400
    assert client.post("/leden/update", json={"row": 2, "field": "kost", "value": 10}).status_code == 400
    assert client.post("/leden/update-all-cost", json={"cost": 10}).status_code == 400

def test_update_member_cost_and_payment(client):
    """Test het updaten van de kostprijs en betaalstatus van een individueel lid."""
    members = storage.get_members()
    assert len(members) > 0
    target_member = members[0]
    target_row = target_member["_excel_row"]

    assert client.post("/leden/update", json={"row": target_row, "field": "kost", "value": 45.5}).status_code == 200
    assert client.post("/leden/update", json={"row": target_row, "field": "betaald", "value": "Ja"}).status_code == 200

    updated_members = storage.get_members()
    updated = next(member for member in updated_members if member["_excel_row"] == target_row)
    assert updated["Kostprijs"] == 45.5
    assert updated["Betaald?"] == "Ja"

def test_update_member_invalid_field(client):
    """Controleer dat het bewerken van een onbestaand veld netjes een 400 fout oplevert."""
    members = storage.get_members()
    assert len(members) > 0
    target_member = members[0]
    target_row = target_member["_excel_row"]

    assert client.post("/leden/update", json={"row": target_row, "field": "onbestaand_veld", "value": "test"}).status_code == 400

def test_update_all_member_costs(client):
    """Test het globaal updaten van de kostprijs voor alle leden tegelijk."""
    initial_members = storage.get_members()
    assert len(initial_members) > 0

    bulk_response = client.post("/leden/update-all-cost", json={"cost": 60.0})
    assert bulk_response.status_code == 200
    assert bulk_response.json() == {"status": "success"}

    after_bulk = storage.get_members()
    assert len(after_bulk) == len(initial_members)
    for member in after_bulk:
        assert member["Kostprijs"] == 60.0

def test_update_all_member_costs_invalid_value(client):
    """Controleer dat het globaal updaten van de kostprijs met een ongeldige waarde een 400 fout oplevert."""
    initial_members = storage.get_members()
    assert len(initial_members) > 0
  
    assert client.post("/leden/update-all-cost", json={"cost": -10.0}).status_code == 400
    assert client.post("/leden/update-all-cost", json={"cost": "ongeldig"}).status_code == 422

def test_regular_member_cannot_update_alcohol_and_sterke(client):
    """Test dat gewone leden (geen leiding) GEEN alcohol of sterke drank kunnen aanpassen (geeft een 400 fout)."""
    members = storage.get_members()
    regular_member = next(member for member in members if "Leiding" not in str(member.get("Tak", "")))
    row = regular_member["_excel_row"]

    alcohol_response = client.post("/leden/update", json={"row": row, "field": "alcohol", "value": "Ja"})
    assert alcohol_response.status_code == 400

    sterke_response = client.post("/leden/update", json={"row": row, "field": "sterke", "value": "Ja"})
    assert sterke_response.status_code == 400

def test_leiding_can_update_alcohol_and_sterke(client):
    """Test dat leiding (of personen met Leiding in hun takken/functies) wel alcohol en sterke drank kunnen aanpassen."""
    members = storage.get_members()
    leiding_member = next(member for member in members if "Leiding" in str(member.get("Tak", "")))
    row = leiding_member["_excel_row"]

    assert client.post("/leden/update", json={"row": row, "field": "alcohol", "value": "Ja"}).status_code == 200
    assert client.post("/leden/update", json={"row": row, "field": "sterke", "value": "Ja"}).status_code == 200

    refreshed = next(member for member in storage.get_members() if member["_excel_row"] == row)
    assert refreshed["Alcohol?"] == "Ja"
    assert refreshed["Sterke?"] == "Ja"

def test_invalid_field_returns_400(client):
    """Controleer dat het bewerken van een onbestaand veld netjes een 400 fout oplevert."""
    members = storage.get_members()
    target_row = members[0]["_excel_row"]

    bad_response = client.post("/leden/update", json={"row": target_row, "field": "onbestaand_veld", "value": "test"})
    assert bad_response.status_code == 400
