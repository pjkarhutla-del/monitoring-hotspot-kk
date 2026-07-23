FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1

ENV LANG id_ID.UTF-8
ENV LANGUAGE id_ID:id
ENV LC_ALL id_ID.UTF-8

RUN apt-get update && apt-get install -y \
    build-essential \
    libgdal-dev \
    gdal-bin \
    locales \
    && sed -i -e 's/# id_ID.UTF-8 UTF-8/id_ID.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]