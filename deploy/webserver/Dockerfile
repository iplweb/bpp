FROM nginx:latest

EXPOSE 80
EXPOSE 443

# Install openssl for certificate generation
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt-get update && apt-get install -y openssl

# Copy both templates - will choose based on environment
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY default.conf.dev.template /etc/nginx/templates/default.conf.dev.template
COPY maintenance.html /usr/share/nginx/html/maintenance.html
COPY 05-ssl-and-template-setup.sh /docker-entrypoint.d/05-ssl-and-template-setup.sh

# Make entrypoint script executable
RUN chmod +x /docker-entrypoint.d/05-ssl-and-template-setup.sh

# Health check for Docker/orchestrators
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f -s -o /dev/null http://127.0.0.1:80/healthz || exit 1
