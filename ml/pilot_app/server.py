"""Adult pilot recorder: runs the 24 cards with a participant and stores one clip per card.

    .venv/Scripts/python pilot_app/server.py        (from ml/)  then open http://localhost:8010

Not part of the game. Listens on 127.0.0.1 only. Everything is written to ml/data/pilot/ (git-ignored):
    participants.csv   code, age band, dialect, date (no names: the signed forms stay on paper)
    p03_17.webm        participant p03, card 17 (the row in pilot_items.csv, from 1)
    clips.csv          path,target,said,... ready for `python pilot.py data/pilot/clips.csv`
`said` starts as what the card asked for; correct it on the review page where a participant read it differently.
"""
import csv
import json
import re
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
DATA = ML / "data" / "pilot"
PAGE = Path(__file__).with_name("index.html")
PORT = 8010
MAX_AUDIO = 5_000_000
CODE = re.compile(r"^p\d{2}$")
CLIP = re.compile(r"^(p\d{2})_(\d{1,2})\.webm$")
CLIP_FIELDS = ["path", "target", "said", "asked", "error", "participant", "card", "recorded_at"]
PEOPLE_FIELDS = ["code", "age_band", "dialect", "date"]
AGE_BANDS = {"18–24", "25–34", "35–49", "50+"}
lock = threading.Lock()  # one writer at a time for the CSV files

with open(ML / "pilot_items.csv", encoding="utf-8") as f:
    ITEMS = list(csv.DictReader(f))


def read(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name: str, fields: list[str], rows: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / (name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(DATA / name)  # never leaves a half-written file behind


def save_clip(code: str, card: int, audio: bytes) -> dict:
    item = ITEMS[card - 1]
    name = f"{code}_{card:02d}.webm"
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_bytes(audio)
    row = {"path": f"data/pilot/{name}", "target": item["target"], "said": item["said"], "asked": item["said"],
           "error": item["error"], "participant": code, "card": card, "recorded_at": datetime.now().isoformat(timespec="seconds")}
    with lock:
        rows = [r for r in read("clips.csv") if r["path"] != row["path"]] + [row]  # a re-recording replaces the clip
        write("clips.csv", CLIP_FIELDS, sorted(rows, key=lambda r: (r["participant"], int(r["card"]))))
    return row


def set_said(path: str, said: str) -> bool:
    with lock:
        rows = read("clips.csv")
        hit = [r for r in rows if r["path"] == path]
        for r in hit:
            r["said"] = said
        write("clips.csv", CLIP_FIELDS, rows)
    return bool(hit)


def delete_participant(code: str) -> int:
    with lock:
        for clip in DATA.glob(f"{code}_*.webm"):
            clip.unlink()
        clips = read("clips.csv")
        write("clips.csv", CLIP_FIELDS, [r for r in clips if r["participant"] != code])
        write("participants.csv", PEOPLE_FIELDS, [r for r in read("participants.csv") if r["code"] != code])
    return len([r for r in clips if r["participant"] == code])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/state":
            return self._json(200, {"items": ITEMS, "clips": read("clips.csv"), "participants": read("participants.csv")})
        if path.startswith("/audio/") and CLIP.match(name := path[len("/audio/"):]) and (DATA / name).exists():
            return self._send(200, (DATA / name).read_bytes(), "audio/webm")
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path, _, query = self.path.partition("?")
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_AUDIO:
            return self._json(413, {"error": "too large"})
        body = self.rfile.read(length)
        try:
            if path == "/api/clip":
                args = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
                code, card = args.get("code", ""), int(args.get("card", 0))
                if not CODE.match(code) or not 1 <= card <= len(ITEMS) or len(body) < 1000:
                    return self._json(422, {"error": "bad code, card or empty recording"})
                return self._json(200, save_clip(code, card, body))
            req = json.loads(body or b"{}")
            if path == "/api/participant":
                code = req.get("code", "")
                if not CODE.match(code) or req.get("age_band") not in AGE_BANDS or not req.get("consent"):
                    return self._json(422, {"error": "code like p01, an age band, and the consent form on file"})
                with lock:
                    people = [r for r in read("participants.csv") if r["code"] != code]
                    people.append({"code": code, "age_band": req["age_band"], "dialect": str(req.get("dialect", ""))[:40],
                                   "date": date.today().isoformat()})
                    write("participants.csv", PEOPLE_FIELDS, people)
                return self._json(200, {"ok": True})
            if path == "/api/said":
                said = str(req.get("said", "")).strip()[:60]
                return self._json(200 if set_said(str(req.get("path", "")), said) else 404, {"ok": True})
            if path == "/api/delete":
                code = req.get("code", "")
                if not CODE.match(code):
                    return self._json(422, {"error": "bad code"})
                return self._json(200, {"deleted_clips": delete_participant(code)})
        except (ValueError, KeyError) as e:
            return self._json(400, {"error": type(e).__name__})
        self._json(404, {"error": "not found"})

    def _json(self, code: int, body: dict):
        self._send(code, json.dumps(body, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _send(self, code: int, data: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # keep the console quiet: no words or codes in logs
        pass


if __name__ == "__main__":
    print(f"Pilot recorder on http://localhost:{PORT}  (clips go to {DATA})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
