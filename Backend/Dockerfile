FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app

COPY requirements.txt ./
RUN pip install --requirement requirements.txt

COPY app ./app
COPY pipelines ./pipelines
RUN mkdir --parents /app/data && chown --recursive app:app /app

USER app

FROM base AS api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8014"]

FROM base AS dataset
ENTRYPOINT ["python", "-m", "pipelines.dataset_generation.cli"]

FROM base AS development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8014", "--reload"]
