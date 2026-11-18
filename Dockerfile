# One image for both services: the web service (API + built frontend) and the worker.
# docker-compose.yml runs it locally; Railway will run the same image.

# --- Stage 1: build the React frontend ---------------------------------------
FROM node:26-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- Stage 2: the Python app -------------------------------------------------
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml ./
COPY killshot/ killshot/
COPY migrations/ migrations/
RUN pip install .
# Only the built files come across from stage 1; Node itself isn't in the final image.
COPY --from=web /app/web/dist web/dist
ENV WEB_DIST=/app/web/dist

RUN useradd --create-home killshot
USER killshot
EXPOSE 8000

# Default: the web service. Migrate first, then serve on $PORT (Railway sets it; 8000 locally).
# The worker overrides this with `python -m killshot.worker`.
CMD ["sh", "-c", "python -m killshot.migrate && exec uvicorn killshot.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
