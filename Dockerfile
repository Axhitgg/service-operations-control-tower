FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service_api.py .
COPY init.sql .

EXPOSE 5090

CMD ["gunicorn", "--bind", "0.0.0.0:5090", "service_api:app"]
