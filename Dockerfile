FROM registry.access.redhat.com/ubi9/python-311

WORKDIR /app

COPY ./app /app
COPY requirements.txt ./

RUN pip install uv && uv pip install --no-cache-dir -r requirements.txt

COPY cache_model.py .

ENV PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/tmp/model_cache

CMD ["python", "app/cache_model.py"]
