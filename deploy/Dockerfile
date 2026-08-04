FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user -r requirements.txt


FROM python:3.14-slim AS runtime

ENV TZ=Europe/Moscow \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/news/.local/bin:${PATH}" \
    PYTHONPATH="/home/news/.local/lib/python3.14/site-packages"

RUN getent group news || groupadd --gid 1000 news \
 && id -u news >/dev/null 2>&1 || useradd --uid 1000 --gid news --create-home --shell /bin/bash news \
 && apt-get update \
 && apt-get install -y --no-install-recommends libxml2 libxslt1.1 tzdata curl \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
 && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /home/news/.local
RUN chown -R news:news /home/news/.local

WORKDIR /app
COPY --chown=news:news . /app

USER news

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/metrics > /dev/null || exit 1

ENTRYPOINT ["python", "./spiders_starter.py"]
