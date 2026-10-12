"""SQLite storage: player profiles, every scored attempt (for /progress and weak sounds), each player's level per game."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "phonics.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    player_id TEXT NOT NULL,
    game TEXT NOT NULL,
    day TEXT NOT NULL,
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    target_phonemes TEXT NOT NULL,
    heard_phonemes TEXT NOT NULL,
    correct INTEGER NOT NULL,
    phoneme_accuracy REAL NOT NULL,
    response_ms INTEGER,
    error_type TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_player ON attempts (player_id, day);
CREATE TABLE IF NOT EXISTS levels (
    player_id TEXT NOT NULL,
    game TEXT NOT NULL,
    level INTEGER NOT NULL,
    PRIMARY KEY (player_id, game)
);
CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    interests TEXT NOT NULL
);
"""


class NameTaken(Exception):
    pass


@contextmanager
def connect():
    path = Path(os.getenv("DB_PATH") or DEFAULT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        with con:  # commit on success, roll back on error
            yield con
    finally:
        con.close()


def save_attempt(player_id: str, game: str, target: str, r: dict) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO attempts (player_id, game, day, target, heard, target_phonemes, heard_phonemes,"
            " correct, phoneme_accuracy, response_ms, error_type) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (player_id, game, date.today().isoformat(), target, r["heard"], json.dumps(r["target_phonemes"]),
             json.dumps(r["heard_phonemes"]), r["correct"], r["phoneme_accuracy"], r["response_ms"], r["error_type"]),
        )


def recent_attempts(player_id: str, limit: int = 50) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            "SELECT correct, target_phonemes, heard_phonemes FROM attempts WHERE player_id = ? ORDER BY id DESC LIMIT ?",
            (player_id, limit),
        ).fetchall()
    return [{"correct": bool(c), "target_phonemes": json.loads(t), "heard_phonemes": json.loads(h)} for c, t, h in rows]


def get_level(player_id: str, game: str) -> int:
    with connect() as con:
        row = con.execute("SELECT level FROM levels WHERE player_id = ? AND game = ?", (player_id, game)).fetchone()
    return row[0] if row else 1


def set_level(player_id: str, game: str, level: int) -> None:
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO levels (player_id, game, level) VALUES (?, ?, ?)", (player_id, game, level))


def sessions(player_id: str, game: str | None = None) -> list[dict]:
    """One session per day: word accuracy, phoneme accuracy, mean response time, error counts (mistakes only)."""
    where, args = ("player_id = ? AND game = ?", (player_id, game)) if game else ("player_id = ?", (player_id,))
    with connect() as con:
        days = con.execute(
            f"SELECT day, AVG(correct), AVG(phoneme_accuracy), AVG(response_ms) FROM attempts WHERE {where}"
            " GROUP BY day ORDER BY day",
            args,
        ).fetchall()
        errors = con.execute(
            f"SELECT day, error_type, COUNT(*) FROM attempts WHERE {where} AND error_type != 'none'"
            " GROUP BY day, error_type",
            args,
        ).fetchall()
    out = {day: {"date": day, "accuracy": round(acc, 2), "phoneme_accuracy": round(ph, 2),
                 "avg_response_ms": None if ms is None else round(ms), "errors": {}}
           for day, acc, ph, ms in days}
    for day, err, n in errors:
        out[day]["errors"][err] = n
    return list(out.values())


def create_player(name: str, interests: list[str]) -> dict:
    player = {"player_id": uuid.uuid4().hex, "name": name, "interests": interests}
    try:
        with connect() as con:
            con.execute("INSERT INTO players (player_id, name, interests) VALUES (?, ?, ?)",
                        (player["player_id"], name, json.dumps(interests)))
    except sqlite3.IntegrityError as e:  # names are unique, ignoring case
        raise NameTaken(name) from e
    return player


def list_players() -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT player_id, name, interests FROM players ORDER BY name COLLATE NOCASE").fetchall()
    return [{"player_id": p, "name": n, "interests": json.loads(i)} for p, n, i in rows]


def get_player(player_id: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT name, interests FROM players WHERE player_id = ?", (player_id,)).fetchone()
    return {"player_id": player_id, "name": row[0], "interests": json.loads(row[1])} if row else None
