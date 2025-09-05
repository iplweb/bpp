# Konfiguracja SSL z Let's Encrypt dla BPP

Ta konfiguracja zapewnia automatyczne zarządzanie certyfikatami SSL przy użyciu Let's Encrypt dla aplikacji BPP.

## Przegląd

Konfiguracja wykorzystuje podejście wieloetapowe:
1. **Początkowy serwer HTTP**: Działa na porcie 80 do obsługi wyzwań ACME
2. **Certbot**: Uzyskuje certyfikaty z Let's Encrypt
3. **Serwer HTTPS**: Uruchamia główną aplikację z SSL na porcie 443

## Wymagania wstępne

- Zainstalowane Docker i Docker Compose
- Nazwa domeny wskazująca na serwer
- Porty 80 i 443 dostępne z internetu
- Żadne inne usługi nie używają portów 80 lub 443

## Szybki start

### 1. Przygotowanie środowiska

```bash
# Skopiuj przykładowy plik środowiskowy
cp .env.docker.ssl.example .env.docker

# Edytuj konfigurację
nano .env.docker
```

**Wymagana konfiguracja:**
- `SITE_NAME`: Twoja nazwa domeny (np. `bpp.uniwersytet.edu.pl`)
- `ADMIN_EMAIL`: Email do powiadomień Let's Encrypt
- `SECRET_KEY`: Wygeneruj bezpieczny klucz Django
- `DATABASE_URL`: Ciąg połączenia z bazą danych

### 2. Uruchomienie skryptu konfiguracyjnego

```bash
# Nadaj uprawnienia wykonywania skryptowi
chmod +x deploy/ssl-setup.sh

# Uruchom konfigurację
./deploy/ssl-setup.sh
```

Wybierz opcję 1 dla początkowej konfiguracji. Skrypt wykona:
- Uzyskanie certyfikatów SSL
- Uruchomienie wszystkich usług
- Konfigurację HTTPS

### 3. Alternatywa: Ręczna konfiguracja

Jeśli preferujesz ręczną konfigurację:

```bash
# Najpierw uruchom serwer HTTP i uzyskaj certyfikaty
docker-compose -f docker-compose.ssl.yml --profile ssl-init up -d

# Poczekaj na uzyskanie certyfikatów (sprawdź logi)
docker-compose -f docker-compose.ssl.yml logs -f certbot

# Po uzyskaniu certyfikatów, zrestartuj z HTTPS
docker-compose -f docker-compose.ssl.yml down
docker-compose -f docker-compose.ssl.yml up -d
```

## Architecture

### Services

- **webserver_http**: Nginx server for ACME challenges (port 80)
- **certbot**: Let's Encrypt client for certificate management
- **webserver_https**: Main Nginx server with SSL (ports 80 & 443)
- **appserver**: Django application server
- **db**: PostgreSQL database
- **redis**: Cache and message broker
- **celerybeat**: Scheduled task runner
- **workerserver-***: Background task workers
- **ofelia**: Cron scheduler for container tasks

### Volumes

- `certbot-etc`: SSL certificates (`/etc/letsencrypt`)
- `certbot-var`: Let's Encrypt working directory
- `web-root`: Web root for ACME challenges
- `staticfiles`: Django static files
- `media`: User-uploaded media files
- `postgresql_data`: Database storage
- `redis_data`: Redis persistence

## Certificate Management

### Automatic Renewal

Certificates are automatically renewed weekly via Ofelia cron job:
- Runs every Sunday at 2 AM
- Certificates are renewed if expiring within 30 days

### Manual Renewal

```bash
# Using the setup script
./deploy/ssl-setup.sh
# Choose option 3

# Or directly with docker-compose
docker-compose -f docker-compose.ssl.yml run --rm certbot renew
docker-compose -f docker-compose.ssl.yml exec webserver_https nginx -s reload
```

### Check Certificate Status

```bash
# Using the setup script
./deploy/ssl-setup.sh
# Choose option 4

# Or directly
docker-compose -f docker-compose.ssl.yml run --rm certbot certificates
```

## Testing

### Staging Certificates

For testing, use Let's Encrypt staging environment:

```bash
# Using the setup script
./deploy/ssl-setup.sh
# Choose option 5

# Note: Staging certificates are not trusted by browsers
# They are only for testing the setup process
```

### Health Checks

```bash
# Check HTTP server
curl http://your-domain.com/health

# Check HTTPS server
curl https://your-domain.com/health
```

## Security Features

### SSL/TLS Configuration
- TLS 1.2 and 1.3 only
- Strong cipher suites
- OCSP stapling enabled
- SSL session caching

### Security Headers
- Strict-Transport-Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Content-Security-Policy
- Referrer-Policy

### Rate Limiting
- API endpoints: 10 requests/second
- Login endpoints: 5 requests/minute

### Additional Security
- Hidden files blocked
- Backup files blocked
- Uploaded script execution prevented
- Server tokens hidden

## Troubleshooting

### Certificate obtainment fails

1. Check DNS resolution:
```bash
nslookup your-domain.com
```

2. Check port 80 accessibility:
```bash
# From another machine
curl http://your-domain.com/.well-known/acme-challenge/test
```

3. Check certbot logs:
```bash
docker-compose -f docker-compose.ssl.yml logs certbot
```

### HTTPS not working

1. Check if certificates exist:
```bash
docker-compose -f docker-compose.ssl.yml run --rm --entrypoint sh certbot \
  -c "ls -la /etc/letsencrypt/live/certyfikaty_ssl/"
```

2. Check nginx configuration:
```bash
docker-compose -f docker-compose.ssl.yml exec webserver_https nginx -t
```

3. Check nginx error logs:
```bash
docker-compose -f docker-compose.ssl.yml logs webserver_https
```

### Rate Limits

Let's Encrypt has rate limits:
- 50 certificates per domain per week
- 5 duplicate certificates per week
- 300 new orders per account per 3 hours

If you hit rate limits, use staging certificates for testing.

## Monitoring

### Logs

View logs for all services:
```bash
docker-compose -f docker-compose.ssl.yml logs -f
```

View logs for specific service:
```bash
docker-compose -f docker-compose.ssl.yml logs -f webserver_https
```

### Service Status

```bash
docker-compose -f docker-compose.ssl.yml ps
```

## Backup

### Backup Certificates

```bash
# Create backup
docker run --rm -v bpp_certbot-etc:/data -v $(pwd):/backup \
  alpine tar czf /backup/letsencrypt-backup.tar.gz -C /data .

# Restore backup
docker run --rm -v bpp_certbot-etc:/data -v $(pwd):/backup \
  alpine tar xzf /backup/letsencrypt-backup.tar.gz -C /data
```

## Clean Start

To remove all SSL configuration and start fresh:

```bash
# Stop all services
docker-compose -f docker-compose.ssl.yml down

# Remove volumes
docker volume rm bpp_certbot-etc bpp_certbot-var bpp_web-root

# Start fresh
./deploy/ssl-setup.sh
```

## Production Checklist

- [ ] Domain DNS configured correctly
- [ ] Firewall allows ports 80 and 443
- [ ] Environment variables configured in `.env.docker`
- [ ] Strong `SECRET_KEY` generated
- [ ] `DEBUG=False` in production
- [ ] Database credentials secured
- [ ] Email configuration for notifications
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented
- [ ] Log rotation configured
- [ ] Security headers verified
- [ ] Rate limiting tested

## Support

For issues with:
- **Let's Encrypt**: Check https://letsencrypt.org/docs/
- **Certbot**: Check https://certbot.eff.org/docs/
- **Nginx**: Check https://nginx.org/en/docs/
- **BPP Application**: Check BPP documentation
