"""SQLite storage: accounts and logins, every scored attempt (for /progress and weak sounds), each player's level per game."""
import hashlib
import hmac
import json
import os
import sqlite3
import secrets
import time
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
CREATE TABLE IF NOT EXISTS accounts (
    player_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    interests TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logins (
    token_hash TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


LOGIN_DAYS = 30


class NameTaken(Exception):
    pass


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()  # a leaked database can't be used to log in


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


def create_account(name: str, password: str, interests: list[str]) -> dict:
    salt = secrets.token_bytes(16)
    player = {"player_id": uuid.uuid4().hex, "name": name, "interests": interests}
    try:
        with connect() as con:
            con.execute("INSERT INTO accounts (player_id, name, password_hash, interests) VALUES (?, ?, ?, ?)",
                        (player["player_id"], name, salt.hex() + "$" + _hash_password(password, salt).hex(),
                         json.dumps(interests)))
    except sqlite3.IntegrityError as e:  # names are unique, ignoring case
        raise NameTaken(name) from e
    return player


def check_password(name: str, password: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT player_id, name, password_hash, interests FROM accounts WHERE name = ?",
                          (name,)).fetchone()
    if not row:
        return None
    salt, stored = row[2].split("$")
    if not hmac.compare_digest(_hash_password(password, bytes.fromhex(salt)).hex(), stored):
        return None
    return {"player_id": row[0], "name": row[1], "interests": json.loads(row[3])}


def start_login(player_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with connect() as con:
        con.execute("INSERT INTO logins (token_hash, player_id, created_at) VALUES (?, ?, ?)",
                    (_hash_token(token), player_id, time.time()))
    return token


def player_for_token(token: str) -> str | None:
    with connect() as con:
        row = con.execute("SELECT player_id FROM logins WHERE token_hash = ? AND created_at > ?",
                          (_hash_token(token), time.time() - LOGIN_DAYS * 86400)).fetchone()
    return row[0] if row else None


def end_login(token: str) -> None:
    with connect() as con:
        con.execute("DELETE FROM logins WHERE token_hash = ?", (_hash_token(token),))


def get_player(player_id: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT name, interests FROM accounts WHERE player_id = ?", (player_id,)).fetchone()
    return {"player_id": player_id, "name": row[0], "interests": json.loads(row[1])} if row else None
