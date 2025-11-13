#!/bin/bash
set -e

# Function to generate self-signed certificates
generate_snakeoil_certs() {
    echo "Generating self-signed SSL certificates for development..."

    # Create directory for certificates if it doesn't exist
    mkdir -p /etc/ssl/private

    # Generate a private key
    openssl genrsa -out /etc/ssl/private/key.pem 2048

    # Generate a self-signed certificate
    openssl req -new -x509 -key /etc/ssl/private/key.pem -out /etc/ssl/private/cert.pem -days 365 \
        -subj "/C=XX/ST=State/L=City/O=Development/OU=BPP/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:::1"

    echo "Self-signed certificates generated successfully!"
    echo "WARNING: These are development certificates only. Browsers will show security warnings."
}

# Remove the dev template to prevent duplicate processing
# We'll use the production template for both dev and production modes
rm -f /etc/nginx/templates/default.conf.dev.template

# Determine which template to use
USE_DEV_TEMPLATE=${USE_DEV_TEMPLATE:-true}
if [ "$USE_DEV_TEMPLATE" = "true" ] || [ "$USE_DEV_TEMPLATE" = "1" ]; then
    echo "Using development mode (auto-generates certificates if needed)"
    # Check if certificates exist and are valid
    if [ ! -f /etc/ssl/private/cert.pem ] || [ ! -f /etc/ssl/private/key.pem ]; then
        echo "SSL certificates not found. Generating self-signed certificates..."
        generate_snakeoil_certs
    else
        echo "Existing SSL certificates found."
        # Check if certificates are expiring soon (within 30 days)
        if openssl x509 -checkend 2592000 -noout -in /etc/ssl/private/cert.pem; then
            echo "Certificates are valid."
        else
            echo "Certificates are expiring soon or expired. Regenerating..."
            generate_snakeoil_certs
        fi
    fi
else
    echo "Using production mode (requires existing certificates)"
    # Verify certificates exist for production mode
    if [ ! -f /etc/ssl/private/cert.pem ] || [ ! -f /etc/ssl/private/key.pem ]; then
        echo "ERROR: SSL certificates not found in production mode!"
        echo "Please mount certificates to /etc/ssl/private/cert.pem and /etc/ssl/private/key.pem"
        echo "Or set USE_DEV_TEMPLATE=true to use auto-generated development certificates"
        exit 1
    fi
fi

# Script complete - nginx's entrypoint will handle starting nginx
echo "SSL and template setup complete. Proceeding with nginx startup..."
