# These are automatically provided by BuildKit but must be declared before use
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

FROM --platform=$BUILDPLATFORM harbor.ssi.com.vn/public/golang:1.25 AS builder

WORKDIR /app

# Route APT through SSI JFrog Artifactory (public Debian mirror is blocked by TLS interception).
# Base image ships /etc/apt/sources.list.d/debian.sources (deb822) pointing at deb.debian.org;
# remove it so APT only sees the JFrog mirrors below.
RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && echo "deb https://jfrog.ssi.com.vn/artifactory/debian/ trixie main" > /etc/apt/sources.list \
    && echo "deb https://jfrog.ssi.com.vn/artifactory/debian/ trixie-updates main" >> /etc/apt/sources.list \
    && echo "deb https://jfrog.ssi.com.vn/artifactory/debian-security/ trixie-security main" >> /etc/apt/sources.list

# Install build dependencies in a separate layer for better caching
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*

# Trust SSI internal CA (needed for TLS interception on go mod download)
COPY ssi.pem /usr/local/share/ca-certificates/ssi-ca.crt
RUN update-ca-certificates

# Route Go module downloads through SSI JFrog Artifactory (proxy.golang.org is blocked by TLS interception)
ENV GOPROXY="https://jfrog.ssi.com.vn/artifactory/api/go/ssi-registry-golang-virtual" \
    GONOSUMCHECK=1 \
    GOSUMDB=off

# Copy go mod and sum files first (better layer caching)
COPY go.mod go.sum ./

# Download dependencies in a separate cached layer
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download && go mod verify

# Copy source code
COPY . .

# Cross-compile the application with enhanced caching
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -ldflags="-w -s" -trimpath -o trino-mcp ./cmd/

# Use a small image for the final container (explicit target platform)
FROM --platform=$TARGETPLATFORM harbor.ssi.com.vn/cicd/alpinetag@sha256:e77e3f5d669af38709829280b28d6a14d8d7a50adf893cd8302c744ab729cd44
# apk update bi chan boi TLS interception noi bo khi goi ra dl-cdn.alpinelinux.org
# RUN apk update && apk --no-cache add ca-certificates

WORKDIR /app

# Copy the binary from the builder stage
COPY --from=builder /app/trino-mcp .

# Trust SSI internal CA at runtime
COPY ssi.pem /usr/local/share/ca-certificates/ssi-ca.crt
RUN update-ca-certificates

# Default environment variables
ENV TRINO_HOST="trino" \
    TRINO_PORT="8080" \
    TRINO_USER="trino" \
    TRINO_CATALOG="memory" \
    TRINO_SCHEMA="default" \
    MCP_TRANSPORT="http" \
    MCP_HOST="0.0.0.0" \
    MCP_PORT="8080"

# Expose the port
EXPOSE ${MCP_PORT}

# Base image sets ENTRYPOINT ["git"]; override it so CMD runs directly
ENTRYPOINT []

# Run the application
CMD ["./trino-mcp"]
