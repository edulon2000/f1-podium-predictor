# syntax=docker/dockerfile:1
# Serving image: FastAPI + the built React app. No pandas/model inside — the API only reads
# the JSON exported to site_data/ by `f1pred-export`.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SITE_DATA_DIR=/app/site_data \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app
RUN pip install --no-cache-dir "fastapi==0.162.2" "uvicorn[standard]==0.54.0"
COPY src/f1pred/__init__.py src/f1pred/__init__.py
COPY src/f1pred/api src/f1pred/api
COPY site_data site_data
COPY --from=web /web/dist frontend/dist
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
# Render (and most PaaS) inject $PORT.
CMD ["sh", "-c", "uvicorn f1pred.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
