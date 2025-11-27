##########
# Builder stage: install dependencies into a virtualenv
##########
FROM registry.access.redhat.com/ubi9/python-311 AS builder

WORKDIR /build

COPY requirements.txt ./
COPY requirements.dev.txt ./

ARG INSTALL_DEV=false
# Proxy/CA support during build (optional; values can be passed via --build-arg)
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

# Create the virtualenv in /tmp (writable for non-root) to avoid permission issues
RUN python -m venv /tmp/venv \
 && . /tmp/venv/bin/activate \
 && python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_DEV" = "true" ]; then python -m pip install --no-cache-dir -r requirements.dev.txt; fi

##########
# Runtime stage: copy only the venv and app sources
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

WORKDIR /app

COPY --from=builder /tmp/venv /app/.venv
COPY ./app /app

CMD ["/app/.venv/bin/python", "cache_model.py"]
