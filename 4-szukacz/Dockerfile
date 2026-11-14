FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY szukacz ./szukacz

ENV SZUKACZ_DATA_DIR=/data/earth
EXPOSE 8002
CMD ["uvicorn", "szukacz.api:app", "--host", "0.0.0.0", "--port", "8002"]
