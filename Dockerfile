# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS dependencies

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
COPY amandaye_backend/requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --require-hashes -r /tmp/requirements.txt

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AMANDAYE_SKIP_DOTENV=1 \
    DJANGO_ENV=production \
    DJANGO_SETTINGS_MODULE=amandaye_backend.settings
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app/amandaye_backend
COPY --chown=app:app amandaye_backend/ ./
COPY --chmod=0555 docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN mkdir -p staticfiles && chown app:app staticfiles
USER app
EXPOSE 8000
ENTRYPOINT ["backend-entrypoint"]
CMD ["gunicorn", "amandaye_backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "30", "--worker-tmp-dir", "/dev/shm", "--max-requests", "1000", "--max-requests-jitter", "100", "--error-logfile", "-"]
