FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN adduser --disabled-password --gecos "" datia
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc unixodbc-dev libpq-dev && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
COPY . /app
RUN chown -R datia:datia /app
USER datia
ENV DJANGO_SETTINGS_MODULE=config.settings
ENV DATIA_LOG_FILE=/app/logs/datia.log
CMD ["python","manage.py","serveboth"]
