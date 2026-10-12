import json
import sqlite3

from app import brain, db

SAM = {"name": "  Sam ", "password": "correct-horse", "interests": ["football", " space "]}


def register(client, body=SAM):
    return client.post("/players", json=body)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_logs_you_in(client):
    r = register(client)
    assert r.status_code == 201
    sam = r.json()
    assert (sam["name"], sam["interests"], len(sam["player_id"])) == ("Sam", ["football", "space"], 32)
    me = client.get("/me", headers=bearer(sam["token"])).json()
    assert me == {"player_id": sam["player_id"], "name": "Sam", "interests": ["football", "space"]}


def test_login_and_logout(client):
    pid = register(client).json()["player_id"]
    r = client.post("/login", json={"name": "sam", "password": "correct-horse"})  # name ignores case
    assert r.status_code == 200 and r.json()["player_id"] == pid
    token = r.json()["token"]
    assert client.post("/logout", headers=bearer(token)).status_code == 204
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_wrong_name_or_password(client):
    register(client)
    assert client.post("/login", json={"name": "Sam", "password": "wrong-password"}).status_code == 401
    assert client.post("/login", json={"name": "Nobody", "password": "correct-horse"}).status_code == 401


def test_rejects_bad_registrations(client):
    register(client)
    assert register(client, {**SAM, "name": "SAM"}).status_code == 409             # taken, ignoring case
    assert register(client, {**SAM, "name": "   "}).status_code == 422
    assert register(client, {**SAM, "name": "x" * 31}).status_code == 422
    assert register(client, {**SAM, "name": "Al", "password": "short"}).status_code == 422
    assert register(client, {**SAM, "name": "Al", "interests": ["a"] * 6}).status_code == 422


def test_password_and_token_are_not_stored_in_clear(client, tmp_path):
    token = register(client).json()["token"]
    dump = "\n".join(sqlite3.connect(tmp_path / "test.db").iterdump())
    assert "correct-horse" not in dump and token not in dump


def test_needs_login(client):
    pid = register(client).json()["player_id"]
    assert client.get("/me").status_code == 401
    assert client.get(f"/progress/{pid}").status_code == 401
    assert client.get(f"/progress/{pid}", headers=bearer("made-up")).status_code == 401
    assert client.post("/score", data={"target": "dog"}, headers=bearer("made-up")).status_code == 401


def test_cannot_read_another_players_data(client, login):
    sam, sam_auth = login(client, "sam")
    alex, _ = login(client, "alex")
    assert client.get(f"/progress/{alex}", headers=sam_auth).status_code == 403
    body = {"player_id": alex, "game": "word_flash", "history": []}
    assert client.post("/next-exercise", json=body, headers=sam_auth).status_code == 403
    assert client.post("/story", json={"player_id": alex}, headers=sam_auth).status_code == 403


def test_logins_expire(client, monkeypatch):
    token = register(client).json()["token"]
    monkeypatch.setattr(db, "LOGIN_DAYS", 0)
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_accounts_are_real_in_mock_mode(mock_client):
    token = register(mock_client).json()["token"]
    assert mock_client.get("/me", headers=bearer(token)).json()["name"] == "Sam"


def test_browser_may_send_the_token(client):
    r = client.options("/me", headers={"Origin": "https://game.example", "Access-Control-Request-Method": "GET",
                                       "Access-Control-Request-Headers": "authorization"})
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_story_uses_profile_interests(client, monkeypatch):
    prompts = []
    monkeypatch.setattr(brain, "_complete", lambda p: prompts.append(p) or json.dumps({"story": "s", "questions": []}))
    sam = register(client).json()
    client.post("/story", json={"player_id": sam["player_id"]}, headers=bearer(sam["token"]))
    assert "interests: football, space" in prompts[0]


def test_progress_phoneme_accuracy_and_game_filter(client, login):
    pid, auth = login(client)

    def say(target, heard, game):
        client.post("/score", data={"target": target, "heard_text": heard, "game": game}, headers=auth)

    say("dog", "dog", "word_flash")    # 1.0
    say("dog", "bog", "word_flash")    # 0.67
    say("cat", "at", "sound_surgery")  # 0.67
    all_games = client.get(f"/progress/{pid}", headers=auth).json()["sessions"][0]
    assert (all_games["accuracy"], all_games["phoneme_accuracy"]) == (0.33, 0.78)
    flash = client.get(f"/progress/{pid}", params={"game": "word_flash"}, headers=auth).json()["sessions"][0]
    assert (flash["accuracy"], flash["phoneme_accuracy"], flash["errors"]) == (0.5, 0.83, {"letter_reversal": 1})
    assert client.get(f"/progress/{pid}", params={"game": "../x"}, headers=auth).status_code == 422
