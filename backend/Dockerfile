# Build the React UI once, then serve it from the same origin as the Python API.
FROM node:22-slim AS frontend
WORKDIR /ui
RUN npm install --global pnpm@11.19.0
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# Runtime needs no Node, browser, frontend dev server or model weights.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/kazan_events.json ./data/kazan_events.json
COPY data/venue_photos.json ./data/venue_photos.json
# platform-api2.max.ru chains to the Russian Trusted Root CA, which is in neither
# certifi nor the slim image's trust store. Without it every call to MAX fails with
# CERTIFICATE_VERIFY_FAILED. See backend/app/config.py:ssl_context.
COPY certs/ ./certs/
COPY --from=frontend /ui/dist ./frontend/dist

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
