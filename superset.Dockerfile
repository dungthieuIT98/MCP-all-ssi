FROM apache/superset:latest
USER root
RUN /app/.venv/bin/python -m ensurepip && /app/.venv/bin/python -m pip install --quiet authlib sqlalchemy-trino
USER superset
