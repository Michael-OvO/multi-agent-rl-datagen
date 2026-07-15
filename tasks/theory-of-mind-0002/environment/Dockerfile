FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY lib /app/lib
RUN mkdir -p /opt/maf
COPY scenario.json /opt/maf/scenario.json
COPY interview /usr/local/bin/interview
RUN chmod +x /usr/local/bin/interview
