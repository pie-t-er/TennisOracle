# Build from the repo root: docker build -f backend/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY ATP_Matches/ ATP_Matches/
COPY backend/ backend/

RUN pip install --no-cache-dir -r backend/requirements.txt

WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
