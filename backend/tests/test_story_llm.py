"""/story against a real OpenAI-compatible HTTP server that, like some hosted dev APIs, rejects JSON-schema output."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

STORY = {"story": "Ben the dog kicks a ball.", "questions": [{"q": "Who kicks?", "answer": "Ben"}]}


class NoSchemaServer(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        NoSchemaServer.requests.append(body)
        if "response_format" in body:
            self._send(400, {"error": {"message": "response_format json_schema is not supported", "type": "invalid_request_error"}})
        else:
            content = "Here you go:\n```json\n" + json.dumps(STORY) + "\n```"
            self._send(200, {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                             "choices": [{"index": 0, "finish_reason": "stop",
                                          "message": {"role": "assistant", "content": content}}]})

    def _send(self, status, payload):
        out = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@pytest.fixture
def no_schema_llm(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), NoSchemaServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("VLLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    monkeypatch.setenv("VLLM_MODEL", "test-model")
    NoSchemaServer.requests = []
    yield NoSchemaServer.requests
    server.shutdown()


def test_story_works_without_schema_support(client, login, no_schema_llm):
    pid, auth = login(client)
    r = client.post("/story", json={"player_id": pid, "interests": ["football"]}, headers=auth)
    assert r.status_code == 200 and r.json() == STORY
    assert ["response_format" in req for req in no_schema_llm] == [True, False]  # tried the schema first
