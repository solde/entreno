FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py core.py db.py nutri.py casas.py public_auth.py ./
COPY data ./data
COPY templates ./templates
COPY static ./static
RUN mkdir -p /data && chown 65534:65534 /data
EXPOSE 8080
USER 65534
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "1", "--threads", "12", "-k", "gthread", "--timeout", "60", "--access-logfile", "-", "app:app"]
