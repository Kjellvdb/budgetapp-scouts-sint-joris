from app import session_store, storage

def test_summary_renders(client):
    """Controleer dat de overzichtspagina correct laadt met een actieve sessie."""
    response = client.get("/overzicht/")
    assert response.status_code == 200
    assert "Overzicht" in response.text

def test_summary_without_session_returns_400(client):
    """Controleer dat overzichtsroutes zonder actieve sessie een 400 fout geven."""
    session_store.clear()
    assert client.get("/overzicht/").status_code == 400
    assert client.post("/overzicht/update-rest", json={"naam": "Jasper Claes", "value": True}).status_code == 400
    assert client.get("/overzicht/grafieken").status_code == 400

def test_summary_totals_and_categories(populated_summary_client):
    """Controleer de totale inkomsten, uitgaven per categorie en nettowinst/omzet."""
    assert len(storage.get_visitors()) == 10
    assert len(storage.get_expenses()) == 21

    summary, person_rows = storage.get_summary()

    assert round(summary.algemeen, 2) == 250.00
    assert round(summary.alcohol, 2) == 180.00
    assert round(summary.sterke_drank, 2) == 70.00
    assert round(summary.persoonlijk, 2) == 40.00
    assert round(summary.uitgaven, 2) == 540.00

    assert round(summary.leden, 2) == 1205.00
    assert round(summary.leiding, 2) == 572.00
    assert round(summary.fourage, 2) == 390.00

    assert round(summary.inkomsten, 2) == 2167.00
    assert round(summary.omzet, 2) == 1627.00

    assert len(person_rows) == 20

def test_summary_individual_drink_and_personal_shares(populated_summary_client):
    """Controleer de individuele verdeling van alcohol (€20), sterke drank (€10), persoonlijke kosten en openstaand saldo."""
    _, person_rows = storage.get_summary()
    by_name = {person.naam: person for person in person_rows}

    jasper = by_name["Jasper Claes"]
    assert round(jasper.kostprijs_basis, 2) == 50.00
    assert round(jasper.alcohol_aandeel, 2) == 20.00
    assert round(jasper.sterke_aandeel, 2) == 10.00
    assert round(jasper.persoonlijk_aandeel, 2) == 12.00
    assert round(jasper.kostprijs_totaal, 2) == 92.00
    assert round(jasper.nog_te_betalen, 2) == 92.00

    lander = by_name["Lander Vandevelde"]
    assert round(lander.alcohol_aandeel, 2) == 20.00
    assert round(lander.sterke_aandeel, 2) == 0.00
    assert round(lander.persoonlijk_aandeel, 2) == 0.00
    assert round(lander.nog_te_betalen, 2) == 70.00

    simon = by_name["Simon De Smet"]
    assert round(simon.alcohol_aandeel, 2) == 0.00
    assert round(simon.sterke_aandeel, 2) == 10.00
    assert round(simon.nog_te_betalen, 2) == 60.00

    bezoeker1 = by_name["Bezoeker 1"]
    assert round(bezoeker1.kostprijs_basis, 2) == 15.00
    assert round(bezoeker1.alcohol_aandeel, 2) == 20.00
    assert round(bezoeker1.sterke_aandeel, 2) == 0.00
    assert round(bezoeker1.persoonlijk_aandeel, 2) == 15.00
    assert round(bezoeker1.kostprijs_totaal, 2) == 50.00
    assert round(bezoeker1.nog_te_betalen, 2) == 35.00

    bezoeker6 = by_name["Bezoeker 6"]
    assert round(bezoeker6.kostprijs_basis, 2) == 10.00
    assert round(bezoeker6.alcohol_aandeel, 2) == 0.00
    assert round(bezoeker6.sterke_aandeel, 2) == 10.00
    assert round(bezoeker6.nog_te_betalen, 2) == 20.00

    bezoeker9 = by_name["Bezoeker 9"]
    assert round(bezoeker9.alcohol_aandeel, 2) == 20.00
    assert round(bezoeker9.sterke_aandeel, 2) == 10.00
    assert round(bezoeker9.nog_te_betalen, 2) == 30.00

def test_summary_view_render_and_excel_export(populated_summary_client):
    """Controleer of /overzicht/ correct laadt, de drinker-info toont en het Overzicht-tabblad wegschrijft in Excel."""
    response = populated_summary_client.get("/overzicht/")
    assert response.status_code == 200
    assert "alcohol ÷ 9 drinkers" in response.text
    assert "sterke drank ÷ 7 drinkers" in response.text
    assert "2167.00" in response.text
    assert "540.00" in response.text
    assert "1627.00" in response.text

    sheet = storage.get_sheet(storage.SHEET_SUMMARY)
    first_col_values = [row[0] for row in sheet.iter_rows(values_only=True) if row and row[0]]
    assert "--- INKOMSTEN ---" in first_col_values
    assert "--- UITGAVEN PER CATEGORIE ---" in first_col_values
    assert "--- FINANCIEEL RESULTAAT ---" in first_col_values
    assert "--- REST BETAALD ---" in first_col_values

def test_update_rest_betaald(populated_summary_client):
    """Test het aanvinken en uitvinken van 'rest betaald' voor een persoon in het overzicht."""
    response_true = populated_summary_client.post("/overzicht/update-rest", json={"naam": "Jasper Claes", "value": True})
    assert response_true.status_code == 200
    assert response_true.json() == {"status": "success"}

    _, person_rows = storage.get_summary()
    jasper = next(person for person in person_rows if person.naam == "Jasper Claes")
    assert jasper.rest_betaald is True

    response_false = populated_summary_client.post("/overzicht/update-rest", json={"naam": "Jasper Claes", "value": False})
    assert response_false.status_code == 200

    _, updated_rows = storage.get_summary()
    jasper_after = next(person for person in updated_rows if person.naam == "Jasper Claes")
    assert jasper_after.rest_betaald is False

def test_summary_charts_view(populated_summary_client):
    """Controleer of de grafiekenpagina (/overzicht/grafieken) laadt met de vroegste datum en categoriegegevens."""
    response = populated_summary_client.get("/overzicht/grafieken")
    assert response.status_code == 200
    assert "2026-07-01" in response.text
    assert "Algemeen" in response.text
    assert "Alcohol" in response.text
