FROM python:3.11-slim

WORKDIR /app

# Layer cache: install dependencies before copying app source
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

# Runtime directories (overridden by volume mounts in compose/k8s)
RUN mkdir -p /data /app/media

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
