# The hosted app (Railway or any Docker host): the API, the speech model runtime and the built frontend in one
# image, served from one address. The model itself is not in the image: set ARABIC_SPEECH_MODEL to its Hugging Face
# repo (and HF_TOKEN if the repo is private); it downloads on first start and is cached under /data.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements-speech.txt ./
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt -r requirements-speech.txt
COPY backend/app ./app
COPY content /content
COPY --from=web /web/dist ./static
# /data: mount a volume here so accounts and the downloaded model survive redeploys
ENV MOCK_MODE=0 STATIC_DIR=/app/static DB_PATH=/data/app.db HF_HOME=/data/hf
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
