# Superset + Authlib (required for AUTH_OAUTH / Azure AD login).
# The stock apache/superset image ships without authlib, so OAuth fails at
# startup with "No module named 'authlib'". We add it here.
FROM apache/superset:4.1.1

USER root
RUN pip install --no-cache-dir authlib
USER superset
