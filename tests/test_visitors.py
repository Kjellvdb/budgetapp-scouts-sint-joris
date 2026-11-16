from app import session_store, storage

def test_visitors_render(client):
    """Controleer of de fourage/bezoekerspagina correct laadt wanneer er een actieve sessie is."""
    response = client.get("/fourage/")
    assert response.status_code == 200
    assert "Fourage" in response.text or "Bezoekers" in response.text

def test_visitors_without_session_returns_400(client):
    """Controleer dat fourage-routes zonder actieve sessie netjes een 400 fout geven."""
    session_store.clear()
    assert client.get("/fourage/").status_code == 400
    assert client.post("/fourage/add", data={"naam": "Test", "kostprijs": 10.0}).status_code == 400
    assert client.post("/fourage/update", json={"row": 2, "field": "kost", "value": 15.0}).status_code == 400
    assert client.post("/fourage/delete", json={"rows": [2]}).status_code == 400
    assert client.post("/fourage/update-all-cost", json={"cost": 15.0}).status_code == 400

def test_add_visitor(client):
    """Test het toevoegen van een nieuwe bezoeker/kookouder via de fourage-route."""
    initial_count = len(storage.get_visitors())
    response = client.post(
        "/fourage/add",
        data={
            "naam": "Kookouder Marc",
            "kostprijs": 15.0,
            "betaald": "Ja",
            "alcohol": "Ja",
            "sterke": "Nee"
        },
        follow_redirects=False
    )
    assert response.status_code == 303

    visitors = storage.get_visitors()
    assert len(visitors) == initial_count + 1

    added_visitor = visitors[-1]
    assert added_visitor["Naam"] == "Kookouder Marc"
    assert added_visitor["Kostprijs"] == 15.0
    assert added_visitor["Betaald?"] == "Ja"
    assert added_visitor["Alcohol?"] == "Ja"
    assert added_visitor["Sterke?"] == "Nee"

def test_update_visitor(client):
    """Test het bijwerken van specifieke velden van een individuele bezoeker."""
    client.post(
        "/fourage/add",
        data={"naam": "Bezoeker Tom", "kostprijs": 10.0, "betaald": "Nee", "alcohol": "Nee", "sterke": "Nee"}
    )
    visitors = storage.get_visitors()
    target_visitor = visitors[-1]
    target_row = target_visitor["_excel_row"]

    assert client.post("/fourage/update", json={"row": target_row, "field": "naam", "value": "Hoofdkookouder Tom"}).status_code == 200
    assert client.post("/fourage/update", json={"row": target_row, "field": "kost", "value": 25.0}).status_code == 200
    assert client.post("/fourage/update", json={"row": target_row, "field": "betaald", "value": "Ja"}).status_code == 200
    assert client.post("/fourage/update", json={"row": target_row, "field": "alcohol", "value": "Ja"}).status_code == 200

    refreshed_visitors = storage.get_visitors()
    updated = next(visitor for visitor in refreshed_visitors if visitor["_excel_row"] == target_row)
    assert updated["Naam"] == "Hoofdkookouder Tom"
    assert updated["Kostprijs"] == 25.0
    assert updated["Betaald?"] == "Ja"
    assert updated["Alcohol?"] == "Ja"

def test_update_visitor_invalid_field(client):
    """Controleer dat het bewerken van een onbestaand veld netjes een 400 fout oplevert."""
    client.post(
        "/fourage/add",
        data={"naam": "Bezoeker Lisa", "kostprijs": 12.0, "betaald": "Nee", "alcohol": "Nee", "sterke": "Nee"}
    )
    visitors = storage.get_visitors()
    target_visitor = visitors[-1]
    target_row = target_visitor["_excel_row"]

    assert client.post("/fourage/update", json={"row": target_row, "field": "onbestaand_veld", "value": "test"}).status_code == 400

def test_update_all_visitor_costs(client):
    """Test het globaal updaten van de kostprijs voor alle bezoekers tegelijk."""
    client.post("/fourage/add", data={"naam": "Gast 1", "kostprijs": 10.0})
    client.post("/fourage/add", data={"naam": "Gast 2", "kostprijs": 10.0})

    initial_visitors = storage.get_visitors()
    assert len(initial_visitors) >= 2

    bulk_response = client.post("/fourage/update-all-cost", json={"cost": 20.0})
    assert bulk_response.status_code == 200
    assert bulk_response.json() == {"status": "success"}

    after_bulk = storage.get_visitors()
    for visitor in after_bulk:
        assert visitor["Kostprijs"] == 20.0

def test_update_all_visitor_costs_invalid_value(client):
    """Controleer dat het globaal updaten van de kostprijs met een ongeldige waarde een 400 fout oplevert."""
    client.post("/fourage/add", data={"naam": "Test 1", "kostprijs": 10.0})
    client.post("/fourage/add", data={"naam": "Test 2", "kostprijs": 10.0})

    initial_visitors = storage.get_visitors()
    assert len(initial_visitors) >= 2

    assert client.post("/fourage/update-all-cost", json={"cost": -5.0}).status_code == 400
    assert client.post("/fourage/update-all-cost", json={"cost": "ongeldig"}).status_code == 422

def test_delete_visitors(client):
    """Test het selectief verwijderen van een of meerdere bezoekers."""
    client.post("/fourage/add", data={"naam": "Te Verwijderen Gast", "kostprijs": 10.0})
    visitors = storage.get_visitors()
    target_row = visitors[-1]["_excel_row"]

    delete_response = client.post("/fourage/delete", json={"rows": [target_row]})
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "success"}

    remaining_visitors = storage.get_visitors()
    assert not any(visitor["_excel_row"] == target_row for visitor in remaining_visitors)
