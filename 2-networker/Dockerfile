FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY networker ./networker
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENV CHARAKTERYZATOR_URL=http://charakteryzator:8001
ENV SZUKACZ_URL=http://szukacz:8002
ENV NETWORKER_ALLOW_MOCK_FALLBACK=1

EXPOSE 80 443

CMD ["/app/entrypoint.sh"]
