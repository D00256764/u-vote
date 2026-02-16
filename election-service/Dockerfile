FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY election-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY election-service/app.py .
COPY election-service/templates ./templates
COPY election-service/static ./static

EXPOSE 5005

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5005"]
