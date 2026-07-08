FROM kong:3.9

USER root

ENV KONG_DATABASE=off \
    KONG_DECLARATIVE_CONFIG=/etc/kong/kong.yml \
    KONG_PROXY_ACCESS_LOG=/dev/stdout \
    KONG_ADMIN_ACCESS_LOG=/dev/stdout \
    KONG_PROXY_ERROR_LOG=/dev/stderr \
    KONG_ADMIN_ERROR_LOG=/dev/stderr \
    KONG_ADMIN_LISTEN="0.0.0.0:8001" \
    KONG_PROXY_LISTEN="0.0.0.0:8000"

COPY kong.yml /etc/kong/kong.yml

USER kong

EXPOSE 8000 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD kong health

CMD ["kong", "docker-start"]
