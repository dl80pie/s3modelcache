##########
# Builder stage: install dependencies into a virtualenv
##########
FROM registry.access.redhat.com/ubi9/python-311 AS builder

WORKDIR /build

COPY requirements.txt ./
COPY requirements.dev.txt ./

ARG INSTALL_DEV=false
ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG REQUESTS_CA_BUNDLE
ARG SSL_CERT_FILE
ARG AWS_CA_BUNDLE
ENV http_proxy=$http_proxy \
    https_proxy=$https_proxy \
    no_proxy=$no_proxy \
    HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY \
    REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE \
    SSL_CERT_FILE=$SSL_CERT_FILE \
    AWS_CA_BUNDLE=$AWS_CA_BUNDLE

# Wechsle zu root, erstelle /app mit korrekten Permissions, dann zurück zu default user
USER 0
RUN mkdir -p /app/.venv && chown -R 1001:0 /app && chmod -R g+rwX /app
USER 1001

# Jetzt erstelle virtualenv direkt am finalen Pfad /app/.venv
RUN python -m venv /app/.venv \
 && . /app/.venv/bin/activate \
 && python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_DEV" = "true" ]; then python -m pip install --no-cache-dir -r requirements.dev.txt; fi

##########
# Runtime stage
##########
FROM registry.access.redhat.com/ubi9/python-311 AS runtime

ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG REQUESTS_CA_BUNDLE
ARG SSL_CERT_FILE
ARG AWS_CA_BUNDLE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/tmp/model_cache \
    PATH="/app/.venv/bin:${PATH}" \
    http_proxy=$http_proxy \
    https_proxy=$https_proxy \
    no_proxy=$no_proxy \
    HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY \
    REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE \
    SSL_CERT_FILE=$SSL_CERT_FILE \
    AWS_CA_BUNDLE=$AWS_CA_BUNDLE

# Erstelle /app Verzeichnis mit korrekten Permissions
USER 0
RUN mkdir -p /app && chown -R 1001:0 /app && chmod -R g+rwX /app
USER 1001

WORKDIR /app

COPY --from=builder --chown=1001:0 /app/.venv /app/.venv
COPY --chown=1001:0 ./app /app

CMD ["/app/.venv/bin/python", "cache_model.py"]