FROM nginx:latest

EXPOSE 80
EXPOSE 443

# Install openssl for certificate generation
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

# Copy both templates - will choose based on environment
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY default.conf.dev.template /etc/nginx/templates/default.conf.dev.template
COPY maintenance.html /usr/share/nginx/html/maintenance.html
COPY 05-ssl-and-template-setup.sh /docker-entrypoint.d/05-ssl-and-template-setup.sh

# Make entrypoint script executable
RUN chmod +x /docker-entrypoint.d/05-ssl-and-template-setup.sh
