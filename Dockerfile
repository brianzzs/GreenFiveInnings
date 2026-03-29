FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

COPY . /app

EXPOSE 8000

ENV FLASK_CONFIG=dev \
    HOST=0.0.0.0 \
    PORT=8000 \
    API_KEY_REQUIRED=false

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8000", "--worker-class", "gthread", "--workers", "2", "--threads", "4", "--timeout", "60", "--graceful-timeout", "15", "--keep-alive", "5", "--reload"]
