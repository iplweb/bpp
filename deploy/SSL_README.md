# Konfiguracja SSL z Let's Encrypt dla BPP

Ta konfiguracja zapewnia automatyczne zarządzanie certyfikatami SSL przy użyciu Let's Encrypt dla aplikacji BPP.

## Alternatywa deweloperska

Dla celów deweloperskich dostępna jest również konfiguracja z automatycznie generowanymi certyfikatami self-signed. Szczegóły znajdziesz w `deploy/webserver/README.md`.

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

## Architektura

### Usługi

- **webserver_http**: Serwer Nginx do obsługi wyzwań ACME (port 80)
- **certbot**: Klient Let's Encrypt do zarządzania certyfikatami
- **webserver_https**: Główny serwer Nginx z SSL (porty 80 i 443)
- **appserver**: Serwer aplikacji Django
- **db**: Baza danych PostgreSQL
- **redis**: Pamięć podręczna i broker wiadomości
- **celerybeat**: Wykonywanie zaplanowanych zadań
- **workerserver-***: Procesy wykonujące zadania w tle
- **ofelia**: Harmonogram cron dla zadań kontenerów

### Wolumeny

- `certbot-etc`: Certyfikaty SSL (`/etc/letsencrypt`)
- `certbot-var`: Katalog roboczy Let's Encrypt
- `web-root`: Katalog główny dla wyzwań ACME
- `staticfiles`: Pliki statyczne Django
- `media`: Pliki przesłane przez użytkowników
- `postgresql_data`: Przechowywanie bazy danych
- `redis_data`: Trwałość Redis

## Zarządzanie certyfikatami

### Automatyczne odnawianie

Certyfikaty są automatycznie odnawiane co tydzień przez zadanie cron Ofelia:
- Uruchamiane w każdą niedzielę o 2:00 w nocy
- Certyfikaty są odnawiane jeśli wygasają w ciągu 30 dni

### Ręczne odnawianie

```bash
# Używając skryptu konfiguracyjnego
./deploy/ssl-setup.sh
# Wybierz opcję 3

# Lub bezpośrednio przez docker-compose
docker-compose -f docker-compose.ssl.yml run --rm certbot renew
docker-compose -f docker-compose.ssl.yml exec webserver_https nginx -s reload
```

### Sprawdzanie statusu certyfikatu

```bash
# Używając skryptu konfiguracyjnego
./deploy/ssl-setup.sh
# Wybierz opcję 4

# Lub bezpośrednio
docker-compose -f docker-compose.ssl.yml run --rm certbot certificates
```

## Testowanie

### Certyfikaty testowe (staging)

Do testowania użyj środowiska staging Let's Encrypt:

```bash
# Używając skryptu konfiguracyjnego
./deploy/ssl-setup.sh
# Wybierz opcję 5

# Uwaga: Certyfikaty staging nie są zaufane przez przeglądarki
# Służą tylko do testowania procesu konfiguracji
```

### Sprawdzanie stanu zdrowia

```bash
# Sprawdź serwer HTTP
curl http://twoja-domena.pl/health

# Sprawdź serwer HTTPS
curl https://twoja-domena.pl/health
```

## Funkcje bezpieczeństwa

### Konfiguracja SSL/TLS
- Tylko TLS 1.2 i 1.3
- Silne zestawy szyfrów
- Włączone OCSP stapling
- Buforowanie sesji SSL

### Nagłówki bezpieczeństwa
- Strict-Transport-Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Content-Security-Policy
- Referrer-Policy

### Ograniczanie szybkości
- Punkty końcowe API: 10 żądań/sekundę
- Punkty końcowe logowania: 5 żądań/minutę

### Dodatkowe zabezpieczenia
- Blokowanie ukrytych plików
- Blokowanie plików kopii zapasowych
- Zapobieganie wykonywaniu przesłanych skryptów
- Ukryte tokeny serwera

## Rozwiązywanie problemów

### Niepowodzenie uzyskania certyfikatu

1. Sprawdź rozwiązywanie DNS:
```bash
nslookup twoja-domena.pl
```

2. Sprawdź dostępność portu 80:
```bash
# Z innej maszyny
curl http://twoja-domena.pl/.well-known/acme-challenge/test
```

3. Sprawdź logi certbot:
```bash
docker-compose -f docker-compose.ssl.yml logs certbot
```

### HTTPS nie działa

1. Sprawdź czy certyfikaty istnieją:
```bash
docker-compose -f docker-compose.ssl.yml run --rm --entrypoint sh certbot \
  -c "ls -la /etc/letsencrypt/live/certyfikaty_ssl/"
```

2. Sprawdź konfigurację nginx:
```bash
docker-compose -f docker-compose.ssl.yml exec webserver_https nginx -t
```

3. Sprawdź logi błędów nginx:
```bash
docker-compose -f docker-compose.ssl.yml logs webserver_https
```

### Limity szybkości

Let's Encrypt ma limity szybkości:
- 50 certyfikatów na domenę tygodniowo
- 5 duplikatów certyfikatów tygodniowo
- 300 nowych zamówień na konto co 3 godziny

Jeśli osiągniesz limity, użyj certyfikatów staging do testowania.

## Monitorowanie

### Logi

Wyświetl logi wszystkich usług:
```bash
docker-compose -f docker-compose.ssl.yml logs -f
```

Wyświetl logi konkretnej usługi:
```bash
docker-compose -f docker-compose.ssl.yml logs -f webserver_https
```

### Status usług

```bash
docker-compose -f docker-compose.ssl.yml ps
```

## Kopia zapasowa

### Kopia zapasowa certyfikatów

```bash
# Tworzenie kopii zapasowej
docker run --rm -v bpp_certbot-etc:/data -v $(pwd):/backup \
  alpine tar czf /backup/letsencrypt-backup.tar.gz -C /data .

# Przywracanie kopii zapasowej
docker run --rm -v bpp_certbot-etc:/data -v $(pwd):/backup \
  alpine tar xzf /backup/letsencrypt-backup.tar.gz -C /data
```

## Czysty start

Aby usunąć całą konfigurację SSL i rozpocząć od nowa:

```bash
# Zatrzymaj wszystkie usługi
docker-compose -f docker-compose.ssl.yml down

# Usuń wolumeny
docker volume rm bpp_certbot-etc bpp_certbot-var bpp_web-root

# Rozpocznij od nowa
./deploy/ssl-setup.sh
```

## Lista kontrolna dla produkcji

- [ ] Poprawnie skonfigurowany DNS domeny
- [ ] Firewall zezwala na porty 80 i 443
- [ ] Zmienne środowiskowe skonfigurowane w `.env.docker`
- [ ] Wygenerowany silny `SECRET_KEY`
- [ ] `DEBUG=False` na produkcji
- [ ] Zabezpieczone dane dostępowe do bazy danych
- [ ] Konfiguracja email dla powiadomień
- [ ] Skonfigurowane monitorowanie i alerty
- [ ] Wdrożona strategia kopii zapasowych
- [ ] Skonfigurowana rotacja logów
- [ ] Zweryfikowane nagłówki bezpieczeństwa
- [ ] Przetestowane ograniczanie szybkości

## Wsparcie

W przypadku problemów z:
- **Let's Encrypt**: Sprawdź https://letsencrypt.org/docs/
- **Certbot**: Sprawdź https://certbot.eff.org/docs/
- **Nginx**: Sprawdź https://nginx.org/en/docs/
- **Aplikacja BPP**: Sprawdź dokumentację BPP
