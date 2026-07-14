FROM python:3.11-slim
WORKDIR /app
COPY lib /app/lib
RUN mkdir -p /opt/maf
COPY scenario.json /opt/maf/scenario.json
COPY coord /usr/local/bin/coord
RUN chmod +x /usr/local/bin/coord
