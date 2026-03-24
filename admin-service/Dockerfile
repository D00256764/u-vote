FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY admin-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY admin-service/app.py .
COPY admin-service/templates ./templates
COPY admin-service/static ./static

EXPOSE 5002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002", "--no-access-log"]
