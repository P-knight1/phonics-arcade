import json

from app import brain


def test_create_and_list_players(client):
    r = client.post("/players", json={"name": "  Sam ", "interests": ["football", " space "]})
    assert r.status_code == 201
    sam = r.json()
    assert sam["name"] == "Sam" and sam["interests"] == ["football", "space"] and len(sam["player_id"]) == 32
    client.post("/players", json={"name": "alex"})
    assert [p["name"] for p in client.get("/players").json()["players"]] == ["alex", "Sam"]


def test_names_are_unique_ignoring_case(client):
    client.post("/players", json={"name": "Sam"})
    assert client.post("/players", json={"name": "sam"}).status_code == 409


def test_rejects_bad_profiles(client):
    assert client.post("/players", json={"name": "   "}).status_code == 422
    assert client.post("/players", json={"name": "x" * 31}).status_code == 422
    assert client.post("/players", json={"name": "Sam", "interests": ["a"] * 6}).status_code == 422


def test_players_are_real_in_mock_mode(mock_client):
    pid = mock_client.post("/players", json={"name": "Sam"}).json()["player_id"]
    assert [p["player_id"] for p in mock_client.get("/players").json()["players"]] == [pid]


def test_story_uses_profile_interests(client, monkeypatch):
    prompts = []
    monkeypatch.setattr(brain, "_complete", lambda p: prompts.append(p) or json.dumps({"story": "s", "questions": []}))
    pid = client.post("/players", json={"name": "Sam", "interests": ["space"]}).json()["player_id"]
    client.post("/story", json={"player_id": pid})
    assert "interests: space" in prompts[0]


def test_progress_phoneme_accuracy_and_game_filter(client):
    def say(target, heard, game):
        client.post("/score", data={"target": target, "heard_text": heard, "player_id": "p1", "game": game})

    say("dog", "dog", "word_flash")   # 1.0
    say("dog", "bog", "word_flash")   # 0.67
    say("cat", "at", "sound_surgery")  # 0.67
    all_games = client.get("/progress/p1").json()["sessions"][0]
    assert (all_games["accuracy"], all_games["phoneme_accuracy"]) == (0.33, 0.78)
    flash = client.get("/progress/p1", params={"game": "word_flash"}).json()["sessions"][0]
    assert (flash["accuracy"], flash["phoneme_accuracy"], flash["errors"]) == (0.5, 0.83, {"letter_reversal": 1})
    assert client.get("/progress/p1", params={"game": "../x"}).status_code == 422
