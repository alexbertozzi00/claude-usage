FROM python:3.12-slim

WORKDIR /app

COPY . /app

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8082

EXPOSE 8082

CMD ["python", "cli.py", "dashboard"]
