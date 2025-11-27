##########
# Builder stage: install dependencies into a virtualenv
##########
FROM registry.access.redhat.com/ubi9/python-311 AS builder

WORKDIR /build

COPY requirements.txt ./
COPY requirements.dev.txt ./

ARG INSTALL_DEV=false
RUN python -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements.dev.txt; fi

##########
# Runtime stage: copy only the venv and app sources
##########
FROM registry.access.redhat.com/ubi9/python-311 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/tmp/model_cache \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY ./app /app

CMD ["python", "cache_model.py"]
