ARG BUILD_FROM=python:3.12-slim
FROM $BUILD_FROM

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app

ENV PYTHONUNBUFFERED=1

CMD ["python3", "/app/main.py"]
