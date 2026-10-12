# Voice reading games for dyslexia

Voice-controlled reading practice games. The player reads aloud, and AI models running on an AMD MI300X GPU (ROCm) score the speech one sound at a time. An adaptive layer then picks the next exercises and stories for that player.

> This is a practice and support tool. It is not a medical or clinical product.

## Run locally (mock mode, no GPU needed)

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000. Interactive docs: http://localhost:8000/docs.

Without Docker:

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
MOCK_MODE=1 uvicorn app.main:app --reload        # PowerShell: $env:MOCK_MODE=1; uvicorn app.main:app --reload
python -m pytest
```

## API

See section 4 of [HANDOFF.md](HANDOFF.md). `GET /health` reports whether mock mode is on.

## Architecture

TODO: diagram, AMD droplet setup (`infra/setup_droplet.sh`), models used.

## License

MIT
