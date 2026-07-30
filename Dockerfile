FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOILLENS_PROFILE=demo \
    SOILLENS_DISABLE_SEMANTIC=1 \
    SOILLENS_CACHE_DIR=/app/.cache

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt \
    && adduser --disabled-password --gecos "" soillens \
    && mkdir -p /app/.cache \
    && chown -R soillens:soillens /app

COPY --chown=soillens:soillens app ./app
COPY --chown=soillens:soillens web ./web
COPY --chown=soillens:soillens demo_data ./demo_data

USER soillens

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)); raise SystemExit(0 if data.get('status') == 'ok' and data.get('profile') == 'demo' else 1)"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

