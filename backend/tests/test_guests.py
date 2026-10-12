import json
import sqlite3

from app import brain, db


def start_guest(client, body=None):
    r = client.post("/guest", json=body)
    return r.json()["player_id"], {"Authorization": f"Bearer {r.json()['token']}"}


def rows_for(tmp_path, player_id):
    con = sqlite3.connect(tmp_path / "test.db")
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t} WHERE player_id = ?", (player_id,)).fetchone()[0]
                for t in ("guests", "attempts", "levels", "logins")}
    finally:
        con.close()


def test_guest_plays_like_a_player(client):
    r = client.post("/guest")
    assert r.status_code == 201 and r.json()["name"] == "Guest" and r.json()["token"]
    pid, auth = r.json()["player_id"], {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/me", headers=auth).json() == {"player_id": pid, "name": "Guest", "interests": []}
    client.post("/score", data={"target": "dog", "heard_text": "bog", "game": "word_flash"}, headers=auth)
    assert client.get(f"/progress/{pid}", headers=auth).json()["sessions"][0]["errors"] == {"letter_reversal": 1}
    r = client.post("/next-exercise", json={"player_id": pid, "game": "word_flash", "history": []}, headers=auth)
    assert r.json()["reason"] == "practising d"  # personalised from this visit's mistakes


def test_guests_are_separate(client):
    a, a_auth = start_guest(client)
    b, _ = start_guest(client)
    assert a != b
    assert client.get(f"/progress/{b}", headers=a_auth).status_code == 403


def test_guest_logout_deletes_everything(client, tmp_path):
    pid, auth = start_guest(client)
    client.post("/score", data={"target": "dog", "heard_text": "dog"}, headers=auth)
    client.post("/next-exercise", json={"player_id": pid, "game": "word_flash", "history": []}, headers=auth)
    assert rows_for(tmp_path, pid) == {"guests": 1, "attempts": 1, "levels": 1, "logins": 1}
    assert client.post("/logout", headers=auth).status_code == 204
    assert rows_for(tmp_path, pid) == {"guests": 0, "attempts": 0, "levels": 0, "logins": 0}
    assert client.get("/me", headers=auth).status_code == 401


def test_old_guests_expire_and_are_cleaned_up(client, tmp_path, monkeypatch):
    pid, auth = start_guest(client)
    client.post("/score", data={"target": "dog", "heard_text": "dog"}, headers=auth)
    monkeypatch.setattr(db, "GUEST_HOURS", 0)
    assert client.get("/me", headers=auth).status_code == 401  # expired
    start_guest(client)                                         # next guest clears out expired ones
    assert rows_for(tmp_path, pid) == {"guests": 0, "attempts": 0, "levels": 0, "logins": 0}


def test_logging_out_an_account_keeps_its_data(client, login, tmp_path):
    pid, auth = login(client)
    client.post("/score", data={"target": "dog", "heard_text": "dog"}, headers=auth)
    client.post("/logout", headers=auth)
    assert rows_for(tmp_path, pid)["attempts"] == 1


def test_guest_interests_feed_the_story(client, monkeypatch):
    prompts = []
    monkeypatch.setattr(brain, "_complete", lambda p: prompts.append(p) or json.dumps({"story": "s", "questions": []}))
    pid, auth = start_guest(client, {"interests": ["cooking"]})
    client.post("/story", json={"player_id": pid}, headers=auth)
    assert "interests: cooking" in prompts[0]


def test_guests_work_in_mock_mode(mock_client):
    pid, auth = start_guest(mock_client)
    assert mock_client.get(f"/progress/{pid}", headers=auth).status_code == 200
