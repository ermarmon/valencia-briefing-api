FROM python:3.11-alpine

# gcc + libxml necesarios para compilar lxml (usado por feedparser)
RUN apk add --no-cache gcc musl-dev libxml2-dev libxslt-dev

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY src/ ./src/
COPY run.sh .
RUN chmod +x run.sh

EXPOSE 8099
CMD ["/app/run.sh"]
