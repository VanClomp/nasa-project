# Component 3: Charakteryzator. Build from this folder:  docker build -t charakteryzator .
FROM python:3.12-slim
WORKDIR /app
COPY service/requirements.txt service/requirements.txt
RUN pip install --no-cache-dir -r service/requirements.txt
COPY scripts/ scripts/
COPY service/ service/
COPY outputs/ outputs/
# Maps are not baked into the image: mount the shared volume and point to the Mars geology folder.
ENV MARS_DATA_DIR=/data/mars MOON_DATA_DIR=/data/moon
EXPOSE 8001
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8001"]
