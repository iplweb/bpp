# Nginx SSL Certificate Setup for Development

This directory contains the nginx configuration with automatic SSL certificate generation for development.

## How it works

### Development Mode (Default)
- **Environment Variable**: `USE_DEV_TEMPLATE=true` (default)
- **Behavior**: Automatically generates self-signed certificates if none exist
- **HTTP**: Serves HTTP directly without redirecting to HTTPS
- **HTTPS**: Available with self-signed certificates (browser warnings expected)
- **Usage**: Perfect for local development without manual certificate setup

### Production Mode
- **Environment Variable**: `USE_DEV_TEMPLATE=false`
- **Behavior**: Requires existing certificates mounted to `/etc/ssl/private/`
- **HTTP**: Redirects to HTTPS
- **HTTPS**: Uses provided certificates
- **Usage**: For production or staging with proper certificates

## Certificate Details

### Auto-generated certificates (Development mode)
- **Type**: Self-signed (snakeoil)
- **Validity**: 365 days
- **Subjects**:
  - Common Name: localhost
  - Subject Alternative Names: localhost, *.localhost, 127.0.0.1, ::1
- **Location**: `/etc/ssl/private/cert.pem` and `/etc/ssl/private/key.pem`

### Using custom certificates
1. Mount your certificates to the container at `/etc/ssl/private/`
2. Set `USE_DEV_TEMPLATE=false`
3. Ensure files are named:
   - Certificate: `cert.pem`
   - Private key: `key.pem`

## Docker Compose Configuration

The webserver service in `docker-compose.yml` is configured with:
- Default development mode: `USE_DEV_TEMPLATE=${USE_DEV_TEMPLATE:-true}`
- SSL certificate volume: `ssl_certs:/etc/ssl/private`
- Ports: `1080:80` and `10443:443`

## Usage Examples

### Development (default)
```bash
# Uses auto-generated certificates
docker-compose up webserver
```

### Production
```bash
# Uses mounted certificates
USE_DEV_TEMPLATE=false docker-compose up webserver
```

### With custom certificates
```bash
# Mount your certificates and use production mode
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up webserver
```

## Browser Warnings

When using auto-generated certificates, browsers will show security warnings:
- Chrome: "Your connection is not private"
- Firefox: "Warning: Potential Security Risk Ahead"
- Safari: "This website is not secure"

These warnings are expected for self-signed certificates. Click "Advanced" and "Proceed to localhost" to continue.

## Certificate Auto-renewal

The entrypoint script automatically:
- Checks if certificates exist
- Validates certificate expiration (renews if expiring within 30 days)
- Generates new certificates if needed

This ensures your development environment always has valid certificates.
