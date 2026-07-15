FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY team /usr/local/bin/team
RUN chmod +x /usr/local/bin/team
