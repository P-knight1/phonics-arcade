import json

from app import brain


def typed(client, auth, target, said, game="word_flash"):
    return client.post("/score", data={"target": target, "heard_text": said, "game": game}, headers=auth).json()


def test_stories_unlock_after_enough_practice(client, login, monkeypatch):
    monkeypatch.setattr(brain, "STORY_UNLOCK", 3)
    monkeypatch.setattr(brain, "_complete", lambda prompt: json.dumps({"story": "ذَهَبَ الْوَلَدُ.", "questions": []}))
    pid, auth = login(client)
    status = lambda: client.get(f"/story/status/{pid}", headers=auth).json()
    assert status() == {"unlocked": False, "attempts": 0, "needed": 3}
    assert client.post("/story", json={"player_id": pid}, headers=auth).status_code == 409

    typed(client, auth, "حَبْلْ", "جَبْلْ")
    typed(client, auth, "قَمَرْ", "قَمَرْ")
    typed(client, auth, "ذَهَبَ الْوَلَدُ", "ذَهَبَ الْوَلَدُ", game="story_recall")  # reading stories doesn't count
    assert status()["attempts"] == 2
    typed(client, auth, "قُلْ «سَمَكْ» بِدُونِ «سَـ»|مَكْ", "مَكْ", game="sound_surgery")
    assert status()["unlocked"] and client.post("/story", json={"player_id": pid}, headers=auth).status_code == 200


def test_story_prompt_names_recently_misread_words(client, login, monkeypatch):
    prompts = []
    monkeypatch.setattr(brain, "_complete", lambda prompt: prompts.append(prompt) or json.dumps({"story": "ذَهَبَ الْوَلَدُ.", "questions": []}))
    pid, auth = login(client)
    typed(client, auth, "حَبْلْ", "جَبْلْ")
    typed(client, auth, "قَمَرْ", "قَمَرْ")  # read right: not a mistake
    typed(client, auth, "تَابْ", "بَابْ", game="sound_surgery")  # nonword answers stay out of stories
    client.post("/story", json={"player_id": pid}, headers=auth)
    assert "مؤخرًا: حَبْلْ\n" in prompts[0]


def test_story_status_needs_own_login(client, login):
    pid, auth = login(client)
    other, _ = login(client, "p2")
    assert client.get(f"/story/status/{pid}").status_code == 401
    assert client.get(f"/story/status/{other}", headers=auth).status_code == 403
