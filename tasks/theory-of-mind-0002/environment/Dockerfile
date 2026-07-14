FROM python:3.11-slim
WORKDIR /app
COPY lib /app/lib
RUN mkdir -p /opt/maf
COPY scenario.json /opt/maf/scenario.json
COPY interview /usr/local/bin/interview
RUN chmod +x /usr/local/bin/interview
