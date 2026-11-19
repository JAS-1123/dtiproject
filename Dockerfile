# Build the React frontend.
FROM node:20-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json ./package.json
RUN npm install
COPY frontend/ ./
RUN npm run build

# Run the FastAPI backend and serve the built frontend from the same service.
FROM python:3.11-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-build /src/frontend/dist ./frontend/dist/
EXPOSE 10000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
