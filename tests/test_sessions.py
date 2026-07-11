def _login(client, email="demo@support.ai", password="demo123"):
    response = client.post("/login", json={"email": email, "password": password})
    return response.json()["token"]


def test_multiple_sessions(client):
    token1 = _login(client)
    token2 = _login(client)

    assert token1 != token2

    me1 = client.get("/me", headers={"Authorization": f"Bearer {token1}"})
    me2 = client.get("/me", headers={"Authorization": f"Bearer {token2}"})
    assert me1.status_code == 200
    assert me2.status_code == 200

    sessions = client.get("/sessions", headers={"Authorization": f"Bearer {token1}"})
    assert sessions.status_code == 200
    assert len(sessions.json()["sessions"]) >= 2


def test_revoke_session(client):
    token1 = _login(client)
    _login(client)

    sessions = client.get("/sessions", headers={"Authorization": f"Bearer {token1}"})
    session_list = sessions.json()["sessions"]
    assert len(session_list) >= 1

    session_id = session_list[0]["id"]
    revoke = client.delete(f"/sessions/{session_id}", headers={"Authorization": f"Bearer {token1}"})
    assert revoke.status_code == 200


def test_refresh_session(client):
    token = _login(client)
    refresh = client.post("/sessions/refresh", headers={"Authorization": f"Bearer {token}"})
    assert refresh.status_code == 200
    assert refresh.json()["status"] == "refreshed"
