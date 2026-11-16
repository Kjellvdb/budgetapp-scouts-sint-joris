from fastapi.testclient import TestClient

from app.main import app, PASSWORD, failed_login_attempts

client = TestClient(app)

def test_login_succeed():
    """Test of inloggen met het juiste wachtwoord slaagt en een cookie zet."""
    failed_login_attempts.clear()
    response = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "scouts_auth" in response.cookies

def test_login_fail():
    """Test of inloggen met een verkeerd wachtwoord faalt en terugstuurt met error."""
    failed_login_attempts.clear()
    response = client.post("/login", data={"password": "fout_wachtwoord"}, follow_redirects=False)
    assert response.status_code == 303
    assert "/login?error=1" in response.headers["location"]

def test_login_locked_out():
    """Test of te vaak fout proberen leidt tot een tijdelijke blokkade (lockout)."""
    failed_login_attempts.clear()
    
    for _ in range(4):
        response = client.post("/login", data={"password": "fout_wachtwoord"}, follow_redirects=False)
        assert response.status_code == 303

    response = client.post("/login", data={"password": "fout_wachtwoord"})
    assert response.status_code == 200
    assert "geblokkeerd" in response.text.lower() or "probeer het over" in response.text.lower()
