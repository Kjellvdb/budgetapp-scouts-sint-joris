import io

from app import session_store, storage

def test_new_budget_render(client):
    """Controleer of de pagina om een nieuw budget aan te maken correct laadt."""
    response = client.get("/budget/new")
    assert response.status_code == 200
    assert "Nieuw budget aanmaken" in response.text

def test_create_new_budget(client):
    """Test het aanmaken van een budget en verifieer sessie, tabbladen, aantal rijen en waarden."""
    csv_bytes = """Voornaam;Achternaam;Lidnummer;Geboortedatum;Leeftijd;Functies;Takken;\nLiam;Janssen;1002938475610;09/10/2020;6;KAP;Kapoenen;\nEmma;Peeters;2113849568291;16/06/2020;6;KAP;Kapoenen;\nNoah;Wouters;3224950671382;27/10/2019;7;KAP;Kapoenen;\nMila;Jacobs;4335061782493;07/08/2019;7;KAP;Kapoenen;\nLucas;Mertens;5446172893504;14/12/2018;7;WP;Welpen;\nJulie;Willems;6557283904615;04/12/2018;7;WP;Welpen;\nFinn;Goossens;7668394015726;02/11/2018;8;WP;Welpen;\nNore;Vermeulen;8779405126837;13/10/2018;8;WP;Welpen;\nMilan;Claes;9880516237948;23/05/2018;8;WP;Welpen;\nLotte;Desmet;1991627348059;15/11/2017;9;WP;Welpen;\nArthur;Wouters;2102738459160;27/02/2017;9;WP;Welpen;\nElena;Maes;3213849560271;23/01/2017;9;WP;Welpen;\nLouis;Jacobs;4324950671382;10/12/2014;11;JGJV;Jonggidsen/Jongverkenners;\nFloor;Smets;5435061782493;14/05/2014;12;JGJV;Jonggidsen/Jongverkenners;\nMatteo;Hermans;6546172893504;22/04/2014;12;JGJV;Jonggidsen/Jongverkenners;\nMarie;Wouters;7657283904615;24/08/2013;13;JGJV;Jonggidsen/Jongverkenners;\nRuben;Claes;8768394015726;07/02/2013;13;JGJV;Jonggidsen/Jongverkenners;\nSander;Meertens;9879405126837;18/04/2012;14;GVE;Gidsen/Verkenners;\nHanna;Willems;1980516237948;22/11/2011;14;GVE;Gidsen/Verkenners;\nJonas;Verbeke;2091627348059;12/11/2011;15;GVE;Gidsen/Verkenners;\nLies;De Smet;3102738459160;23/05/2011;15;GVE;Gidsen/Verkenners;\nWout;Vandevelde;4213849560271;19/05/2011;15;GVE;Gidsen/Verkenners;\nKato;Claes;5324950671382;11/05/2011;15;GVE;Gidsen/Verkenners;\nStaf;Wouters;6435061782493;13/12/2010;15;GVE;Gidsen/Verkenners;\nFalke;Jacobs;7546172893504;02/08/2010;16;GVE;Gidsen/Verkenners;\nBrent;Smets;8657283904615;25/09/2009;17;AGRL, AJGV, JIN;Leiding, Jin;\nFemke;Hermans;9768394015726;27/06/2009;17;AKPL, AWPL, JIN;Leiding, Jin;\nKobe;Wouters;1879405126837;16/06/2009;17;AGRL, AKPL, AWPL, JIN;Leiding, Jin;\nAmber;Claes;2980516237948;06/04/2009;17;AGRL, AKPL, AWPL, JIN;Leiding, Jin;\nDaan;Meertens;3091627348059;26/03/2009;17;AJGV, JIN;Leiding, Jin;\nLore;Willems;4102738459160;21/03/2009;17;AKPL, AWPL, JIN;Leiding, Jin;\nWout;Verbeke;5213849560271;09/02/2004;22;AVGA, FV, GRL, GVL, JL, VGA;Leiding, Anderen;\nSimon;De Smet;6324950671382;08/10/2003;23;AVGA, GRL, GRS, JL, LOK, WEB;Leiding, Anderen;\nLander;Vandevelde;7435061782493;02/02/2003;23;GVL;Leiding;\nJasper;Claes;8546172893504;10/02/1995;31;GVL;Leiding;\n""".encode("utf-8")

    response = client.post(
        "/budget/new",
        files={"members_file": ("leden.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"budget_name": "Groepsweekend 2026"},
        follow_redirects=True
    )

    assert response.status_code == 200
    assert "Ledenlijst" in response.text
    assert "Groepsweekend 2026" in response.text
    assert "Liam" in response.text
    assert "Jasper" in response.text

    assert session_store.is_loaded() is True
    assert session_store.get_filename() == "Groepsweekend 2026.xlsx"

    workbook = session_store.get_workbook()
    assert set(workbook.sheetnames) == {
        storage.SHEET_MEMBERS,
        storage.SHEET_VISITORS,
        storage.SHEET_EXPENSES,
        storage.SHEET_SUMMARY,
    }

    members = storage.get_members()
    assert len(members) == 35

    first_member = members[0]
    assert first_member["Naam"] == "Liam Janssen"
    assert first_member["Tak"] == "Kapoenen"
    assert first_member["Kostprijs"] == 0.0
    assert first_member["Betaald?"] == "Nee"
    assert first_member["Alcohol?"] == "Nee"
    assert first_member["Sterke?"] == "Nee"

    last_member = members[-1]
    assert last_member["Naam"] == "Jasper Claes"
    assert last_member["Tak"] == "Leiding"
    assert last_member["Kostprijs"] == 0.0
    assert last_member["Betaald?"] == "Nee"
    assert last_member["Alcohol?"] == "Nee"
    assert last_member["Sterke?"] == "Nee"
