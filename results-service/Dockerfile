FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY results-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY results-service/app.py .
COPY results-service/templates ./templates
COPY results-service/static ./static

EXPOSE 5004

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5004"]
