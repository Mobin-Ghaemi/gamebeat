FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
COPY deploy/requirements.txt /tmp/runtime-requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /tmp/requirements.txt -r /tmp/runtime-requirements.txt \
    && pip check \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=10001:10001 . /app
RUN pip freeze > /app/deploy/requirements.resolved.txt
ENV DJANGO_SETTINGS_MODULE=deploy.settings
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "deploy.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "90", "--max-requests", "1000", "--max-requests-jitter", "100", "--access-logfile", "-", "--error-logfile", "-", "--worker-tmp-dir", "/tmp"]
