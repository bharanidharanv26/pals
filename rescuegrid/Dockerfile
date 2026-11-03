FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000
COPY requirements.lock.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libstdc++6 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ ./backend/
COPY data/ ./data/
COPY scripts/launch.py ./scripts/launch.py
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN useradd --create-home appuser && mkdir -p /app/runtime && chown -R appuser:appuser /app/runtime
USER appuser
EXPOSE 8000
CMD ["python", "scripts/launch.py", "--host", "0.0.0.0", "--no-browser"]
