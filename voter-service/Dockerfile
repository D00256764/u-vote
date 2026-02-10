FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities
COPY shared /app/shared

# Copy service files
COPY voter-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY voter-service/app.py .

EXPOSE 5002

CMD ["python", "app.py"]
