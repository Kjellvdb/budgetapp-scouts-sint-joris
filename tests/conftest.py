from fastapi.testclient import TestClient

import pytest

from app.main import app, PASSWORD, failed_login_attempts
from app import session_store, storage

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset de in-memory mislukte pogingen voor elke test."""
    failed_login_attempts.clear()
    yield
    failed_login_attempts.clear()

@pytest.fixture
def client():
    """Een testclient die een nieuwe sessie heeft en een budgetbestand heeft geladen."""
    csv_bytes = """Voornaam;Achternaam;Lidnummer;Geboortedatum;Leeftijd;Functies;Takken;\nLiam;Janssen;1002938475610;09/10/2020;6;KAP;Kapoenen;\nEmma;Peeters;2113849568291;16/06/2020;6;KAP;Kapoenen;\nNoah;Wouters;3224950671382;27/10/2019;7;KAP;Kapoenen;\nMila;Jacobs;4335061782493;07/08/2019;7;KAP;Kapoenen;\nLucas;Mertens;5446172893504;14/12/2018;7;WP;Welpen;\nJulie;Willems;6557283904615;04/12/2018;7;WP;Welpen;\nFinn;Goossens;7668394015726;02/11/2018;8;WP;Welpen;\nNore;Vermeulen;8779405126837;13/10/2018;8;WP;Welpen;\nMilan;Claes;9880516237948;23/05/2018;8;WP;Welpen;\nLotte;Desmet;1991627348059;15/11/2017;9;WP;Welpen;\nArthur;Wouters;2102738459160;27/02/2017;9;WP;Welpen;\nElena;Maes;3213849560271;23/01/2017;9;WP;Welpen;\nLouis;Jacobs;4324950671382;10/12/2014;11;JGJV;Jonggidsen/Jongverkenners;\nFloor;Smets;5435061782493;14/05/2014;12;JGJV;Jonggidsen/Jongverkenners;\nMatteo;Hermans;6546172893504;22/04/2014;12;JGJV;Jonggidsen/Jongverkenners;\nMarie;Wouters;7657283904615;24/08/2013;13;JGJV;Jonggidsen/Jongverkenners;\nRuben;Claes;8768394015726;07/02/2013;13;JGJV;Jonggidsen/Jongverkenners;\nSander;Meertens;9879405126837;18/04/2012;14;GVE;Gidsen/Verkenners;\nHanna;Willems;1980516237948;22/11/2011;14;GVE;Gidsen/Verkenners;\nJonas;Verbeke;2091627348059;12/11/2011;15;GVE;Gidsen/Verkenners;\nLies;De Smet;3102738459160;23/05/2011;15;GVE;Gidsen/Verkenners;\nWout;Vandevelde;4213849560271;19/05/2011;15;GVE;Gidsen/Verkenners;\nKato;Claes;5324950671382;11/05/2011;15;GVE;Gidsen/Verkenners;\nStaf;Wouters;6435061782493;13/12/2010;15;GVE;Gidsen/Verkenners;\nFalke;Jacobs;7546172893504;02/08/2010;16;GVE;Gidsen/Verkenners;\nBrent;Smets;8657283904615;25/09/2009;17;AGRL, AJGV, JIN;Leiding, Jin;\nFemke;Hermans;9768394015726;27/06/2009;17;AKPL, AWPL, JIN;Leiding, Jin;\nKobe;Wouters;1879405126837;16/06/2009;17;AGRL, AKPL, AWPL, JIN;Leiding, Jin;\nAmber;Claes;2980516237948;06/04/2009;17;AGRL, AKPL, AWPL, JIN;Leiding, Jin;\nDaan;Meertens;3091627348059;26/03/2009;17;AJGV, JIN;Leiding, Jin;\nLore;Willems;4102738459160;21/03/2009;17;AKPL, AWPL, JIN;Leiding, Jin;\nWout;Verbeke;5213849560271;09/02/2004;22;AVGA, FV, GRL, GVL, JL, VGA;Leiding, Anderen;\nSimon;De Smet;6324950671382;08/10/2003;23;AVGA, GRL, GRS, JL, LOK, WEB;Leiding, Anderen;\nLander;Vandevelde;7435061782493;02/02/2003;23;GVL;Leiding;\nJasper;Claes;8546172893504;10/02/1995;31;GVL;Leiding;\n""".encode("utf-8")
    with TestClient(app) as test_client:
        test_client.post("/login", data={"password": PASSWORD})
        response = test_client.get("/")
        assert response.status_code == 200
        session_id = test_client.cookies.get(
            session_store.SESSION_COOKIE_NAME
        )
        assert session_id is not None
        token = session_store.set_session_id(session_id)
        try:
            excel_bytes = storage.create_new_budget(
                "test",
                csv_bytes,
            )
            session_store.load_from_bytes(
                excel_bytes,
                "test.xlsx",
            )
            yield test_client
        finally:
            session_store.clear()
            session_store.reset_session_id(token)

@pytest.fixture
def populated_summary_client(client):
    """Een testclient die een budgetbestand heeft geladen en enkele leden, bezoekers en uitgaven heeft toegevoegd voor samenvattingsdoeleinden."""
    members = storage.get_members()

    leaders = [
        member for member in members
        if "Leiding" in str(member.get("Tak", ""))
    ]

    non_leaders = [
        member for member in members
        if "Leiding" not in str(member.get("Tak", ""))
    ]

    assert client.post(
        "/leden/update-all-cost",
        json={"cost": 50.0},
    ).status_code == 200

    for member in non_leaders[:3]:
        row = member["_excel_row"]

        assert client.post(
            "/leden/update",
            json={"row": row, "field": "kost", "value": 35.0},
        ).status_code == 200

        assert client.post(
            "/leden/update",
            json={"row": row, "field": "betaald", "value": "Ja"},
        ).status_code == 200

    jasper = leaders[-1]
    lander = leaders[-2]
    simon = leaders[-3]

    for member, field in [
        (jasper, "alcohol"),
        (jasper, "sterke"),
        (lander, "alcohol"),
        (simon, "sterke"),
    ]:
        assert client.post(
            "/leden/update",
            json={
                "row": member["_excel_row"],
                "field": field,
                "value": "Ja",
            },
        ).status_code == 200

    visitors_data = [
        {"naam": "Bezoeker 1", "kostprijs": 20.0, "betaald": "Ja", "alcohol": "Ja", "sterke": "Nee"},
        {"naam": "Bezoeker 2", "kostprijs": 20.0, "betaald": "Nee", "alcohol": "Ja", "sterke": "Nee"},
        {"naam": "Bezoeker 3", "kostprijs": 20.0, "betaald": "Ja", "alcohol": "Ja", "sterke": "Nee"},
        {"naam": "Bezoeker 4", "kostprijs": 20.0, "betaald": "Nee", "alcohol": "Ja", "sterke": "Nee"},
        {"naam": "Bezoeker 5", "kostprijs": 20.0, "betaald": "Ja", "alcohol": "Ja", "sterke": "Nee"},
        {"naam": "Bezoeker 6", "kostprijs": 20.0, "betaald": "Nee", "alcohol": "Nee", "sterke": "Ja"},
        {"naam": "Bezoeker 7", "kostprijs": 20.0, "betaald": "Ja", "alcohol": "Nee", "sterke": "Ja"},
        {"naam": "Bezoeker 8", "kostprijs": 20.0, "betaald": "Nee", "alcohol": "Nee", "sterke": "Ja"},
        {"naam": "Bezoeker 9", "kostprijs": 20.0, "betaald": "Ja", "alcohol": "Ja", "sterke": "Ja"},
        {"naam": "Bezoeker 10", "kostprijs": 20.0, "betaald": "Nee", "alcohol": "Ja", "sterke": "Ja"},
    ]

    for visitor in visitors_data:
        assert client.post(
            "/fourage/add",
            data=visitor,
            follow_redirects=False,
        ).status_code == 303

    visitors = storage.get_visitors()

    assert len(visitors) == 10

    assert client.post(
        "/fourage/update",
        json={
            "row": visitors[0]["_excel_row"],
            "field": "kost",
            "value": 15.0,
        },
    ).status_code == 200

    assert client.post(
        "/fourage/update",
        json={
            "row": visitors[5]["_excel_row"],
            "field": "kost",
            "value": 10.0,
        },
    ).status_code == 200

    for index in range(1, 11):
        assert client.post(
            "/uitgaven/add",
            data={
                "datum": f"{index:02d}/07/2026",
                "item": f"Algemeen {index}",
                "aantal": 1,
                "prijs": 25.0,
                "categorie": "Algemeen",
            },
            follow_redirects=False,
        ).status_code == 303

    for index in range(1, 6):
        assert client.post(
            "/uitgaven/add",
            data={
                "datum": "11/07/2026",
                "item": f"Alcohol {index}",
                "aantal": 1,
                "prijs": 36.0,
                "categorie": "Alcohol",
            },
            follow_redirects=False,
        ).status_code == 303

    for index in range(1, 3):
        assert client.post(
            "/uitgaven/add",
            data={
                "datum": "12/07/2026",
                "item": f"Sterke {index}",
                "aantal": 1,
                "prijs": 35.0,
                "categorie": "Sterke drank",
            },
            follow_redirects=False,
        ).status_code == 303

    personal_expenses = [
        {
            "datum": "13/07/2026",
            "item": "Persoonlijk Leiding 1",
            "aantal": 1,
            "prijs": 12.0,
            "categorie": "Persoonlijk",
            "persoon": jasper["Naam"],
            "betaald": "Nee",
        },
        {
            "datum": "13/07/2026",
            "item": "Persoonlijk Leiding 2",
            "aantal": 1,
            "prijs": 8.0,
            "categorie": "Persoonlijk",
            "persoon": lander["Naam"],
            "betaald": "Ja",
        },
        {
            "datum": "14/07/2026",
            "item": "Persoonlijk Bezoeker 1",
            "aantal": 1,
            "prijs": 15.0,
            "categorie": "Persoonlijk",
            "persoon": "Bezoeker 1",
            "betaald": "Nee",
        },
        {
            "datum": "14/07/2026",
            "item": "Persoonlijk Bezoeker 2",
            "aantal": 1,
            "prijs": 5.0,
            "categorie": "Persoonlijk",
            "persoon": "Bezoeker 2",
            "betaald": "Ja",
        },
    ]

    for expense in personal_expenses:
        assert client.post(
            "/uitgaven/add",
            data=expense,
            follow_redirects=False,
        ).status_code == 303

    return client

@pytest.fixture
def authenticated_client():
    """Een testclient die al is ingelogd met de juiste cookie."""
    client = TestClient(app)
    client.post("/login", data={"password": PASSWORD})
    return client
