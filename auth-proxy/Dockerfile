FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proxy.py auth.py mcp_handlers.py trino_handlers.py superset_handlers.py superset_auth.py .

EXPOSE 6275

CMD ["python", "proxy.py"]
