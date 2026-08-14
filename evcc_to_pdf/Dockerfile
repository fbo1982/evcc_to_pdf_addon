FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     libpango-1.0-0     libpangoft2-1.0-0     libcairo2     libgdk-pixbuf-2.0-0     libffi-dev     shared-mime-info     fonts-dejavu-core     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8099", "--timeout", "120", "--graceful-timeout", "8", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "wsgi:application"]
