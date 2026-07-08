FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proxy.py auth.py db.py mcp_handlers.py trino_handlers.py superset_handlers.py superset_auth.py .
COPY migrations ./migrations

EXPOSE 6275

CMD ["python", "proxy.py"]
