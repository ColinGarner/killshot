# The killshot app, as Railway runs it: one image with the API, the worker and
# the built React site. Locally you don't need this (use `killshot start`).

# 1. Build the React site.
FROM node:26.13.1-slim AS site
WORKDIR /web
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# 2. The Python app, with the built site copied in.
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY killshot ./killshot
COPY migrations ./migrations
# Editable, so the code finds migrations/ and web/dist next to it in /app.
RUN pip install --no-cache-dir -e .
COPY --from=site /web/dist ./web/dist
ENV PYTHONUNBUFFERED=1
CMD ["killshot", "serve"]
