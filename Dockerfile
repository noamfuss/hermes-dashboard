# ── Stage 1: build the React frontend ─────────────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + serve built static files ─────────────────────
FROM python:3.13-slim
WORKDIR /app/backend

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy the built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist /app/static

ENV HERMES_HOME=/data \
    STATIC_DIR=/app/static \
    PYTHONUNBUFFERED=1

EXPOSE 8100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
