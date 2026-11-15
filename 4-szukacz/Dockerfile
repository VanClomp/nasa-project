FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY szukacz ./szukacz

# Data folder: /data/earth_real (real Earth data, git-ignored) if present, else /data/earth (mock in git);
# set SZUKACZ_DATA_DIR to override.
EXPOSE 8002
CMD ["uvicorn", "szukacz.api:app", "--host", "0.0.0.0", "--port", "8002"]
