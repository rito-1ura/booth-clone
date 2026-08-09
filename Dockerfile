# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml requirements.txt* /app/
RUN pip install --upgrade pip && \
    if [ -f requirements.txt ]; then \
        pip install -r requirements.txt; \
    else \
        pip install django~=5.1 django-crispy-forms crispy-bootstrap5 \
                    pillow celery[redis] polib gunicorn psycopg2-binary; \
    fi

# ========== Production stage ==========
FROM python:3.11-slim-bookworm AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=booth.settings \
    DJANGO_DEBUG=False

WORKDIR /app

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 gettext \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Compile locale messages
RUN python manage.py compilemessages --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "booth.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
