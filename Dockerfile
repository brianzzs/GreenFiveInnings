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

ENV FLASK_CONFIG=prod \
    HOST=0.0.0.0 \
    PORT=8000

CMD ["sh", "-c", "uvicorn asgi:application --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --timeout-keep-alive 5"]
