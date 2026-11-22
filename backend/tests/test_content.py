import json

import pytest

from app import brain, g2p

GAMES = sorted(p.stem for p in brain.CONTENT_DIR.glob("*.json"))


@pytest.mark.parametrize("game", GAMES)
def test_content_files_are_playable(game):
    levels = brain.load_levels(game)
    assert levels
    for level in levels:
        assert len(level["items"]) >= brain.ROUND_SIZE, level["focus"]
        for item in level["items"]:
            assert g2p.phonemes(item.split("|")[-1]), item  # every target is vowelized Arabic with sounds


def test_sound_surgery_items_have_prompt_and_answer():
    for level in json.loads((brain.CONTENT_DIR / "sound_surgery.json").read_text(encoding="utf-8"))["levels"]:
        for item in level["items"]:
            prompt, answer = item.split("|")
            word = prompt.split("«")[1].split("»")[0]
            assert g2p.phonemes(answer) != g2p.phonemes(word), item


def test_pick_items_targets_the_answer_not_the_prompt():
    items = ["قُلْ «بَابْ»|تَابْ", "قُلْ «تَابْ»|بَابْ"] + [f"قُلْ «سَمَكْ»|مَكْ{i}" for i in range(3)]
    assert brain.pick_items(items, ["t"])[0] == "قُلْ «بَابْ»|تَابْ"
