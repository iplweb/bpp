#!/bin/bash
#
# Skrypt konfiguracji SSL dla BPP z Let's Encrypt
# Ten skrypt zarządza cyklem życia certyfikatów SSL dla wdrożenia BPP
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration file
ENV_FILE=".env.docker"
COMPOSE_FILE="docker-compose.ssl.yml"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_message "$YELLOW" "Sprawdzanie wymagań wstępnych..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_message "$RED" "Błąd: Docker nie jest zainstalowany"
        exit 1
    fi

    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        print_message "$RED" "Błąd: Docker Compose nie jest zainstalowany"
        exit 1
    fi

    # Check if environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        print_message "$RED" "Błąd: Plik $ENV_FILE nie został znaleziony"
        print_message "$YELLOW" "Proszę utworzyć plik $ENV_FILE ze zmiennymi SITE_NAME i ADMIN_EMAIL"
        echo "Przykład:"
        echo "  SITE_NAME=bpp.example.com"
        echo "  ADMIN_EMAIL=admin@example.com"
        exit 1
    fi

    # Check required environment variables
    source "$ENV_FILE"
    if [ -z "$SITE_NAME" ] || [ -z "$ADMIN_EMAIL" ]; then
        print_message "$RED" "Błąd: SITE_NAME i ADMIN_EMAIL muszą być ustawione w pliku $ENV_FILE"
        exit 1
    fi

    print_message "$GREEN" "Sprawdzenie wymagań zakończone pomyślnie"
}

# Function to check if certificates exist
check_certificates() {
    docker-compose -f "$COMPOSE_FILE" run --rm --entrypoint sh certbot \
        -c "test -f /etc/letsencrypt/live/certyfikaty_ssl/fullchain.pem && echo 'EXISTS' || echo 'NOT_FOUND'"
}

# Function to obtain initial certificates
obtain_certificates() {
    print_message "$YELLOW" "Pobieranie certyfikatów SSL dla $SITE_NAME..."

    # Start HTTP server for ACME challenge
    print_message "$YELLOW" "Uruchamianie serwera HTTP dla wyzwania ACME..."
    docker-compose -f "$COMPOSE_FILE" --profile ssl-init up -d webserver_http

    # Wait for HTTP server to be ready
    print_message "$YELLOW" "Oczekiwanie na gotowość serwera HTTP..."
    sleep 10

    # Run certbot to obtain certificates
    print_message "$YELLOW" "Uruchamianie certbot w celu uzyskania certyfikatów..."
    docker-compose -f "$COMPOSE_FILE" --profile ssl-init up certbot

    # Check if certificates were obtained successfully
    if [ "$(check_certificates)" = "EXISTS" ]; then
        print_message "$GREEN" "Certyfikaty SSL zostały pobrane pomyślnie!"
        return 0
    else
        print_message "$RED" "Nie udało się uzyskać certyfikatów SSL"
        print_message "$YELLOW" "Proszę sprawdzić:"
        echo "  1. DNS jest poprawnie skonfigurowany dla $SITE_NAME"
        echo "  2. Port 80 jest dostępny z internetu"
        echo "  3. Żadna zapora nie blokuje wyzwania ACME"
        return 1
    fi
}

# Function to start the full stack
start_stack() {
    print_message "$YELLOW" "Uruchamianie stosu BPP z SSL..."

    # Stop any running services
    docker-compose -f "$COMPOSE_FILE" --profile ssl-init down

    # Start all services with default profile (includes HTTPS)
    docker-compose -f "$COMPOSE_FILE" up -d

    print_message "$GREEN" "Stos BPP został uruchomiony pomyślnie!"
    print_message "$YELLOW" "Dostęp do serwisu: https://$SITE_NAME"
}

# Function to renew certificates
renew_certificates() {
    print_message "$YELLOW" "Odnawianie certyfikatów SSL..."

    docker-compose -f "$COMPOSE_FILE" run --rm certbot renew

    # Reload nginx to use new certificates
    docker-compose -f "$COMPOSE_FILE" exec -T webserver_https nginx -s reload 2>/dev/null || true

    print_message "$GREEN" "Odnowienie certyfikatów zakończone"
}

# Function to show certificate status
show_status() {
    print_message "$YELLOW" "Status certyfikatów:"

    docker-compose -f "$COMPOSE_FILE" run --rm --entrypoint sh certbot \
        -c "certbot certificates --cert-name certyfikaty_ssl 2>/dev/null || echo 'Nie znaleziono certyfikatów'"
}

# Function to test with staging certificates
test_staging() {
    print_message "$YELLOW" "Testowanie ze środowiskiem staging Let's Encrypt..."

    # Backup existing certificates if any
    docker-compose -f "$COMPOSE_FILE" run --rm --entrypoint sh certbot \
        -c "if [ -d /etc/letsencrypt/live/certyfikaty_ssl ]; then mv /etc/letsencrypt/live/certyfikaty_ssl /etc/letsencrypt/live/certyfikaty_ssl.backup; fi"

    # Obtain staging certificates
    docker-compose -f "$COMPOSE_FILE" run --rm certbot certonly \
        --non-interactive \
        --webroot \
        --webroot-path=/var/www/html \
        --email "$ADMIN_EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$SITE_NAME" \
        --cert-name certyfikaty_ssl \
        --staging \
        --force-renewal

    print_message "$GREEN" "Certyfikaty testowe zostały pobrane (tylko do testów)"
}

# Function to cleanup and start fresh
cleanup() {
    print_message "$YELLOW" "Czyszczenie certyfikatów SSL i woluminów..."

    read -r -p "To usunie wszystkie certyfikaty. Czy jesteś pewien? (t/N) " -n 1
    echo
    if [[ $REPLY =~ ^[Tt]$ ]]; then
        docker-compose -f "$COMPOSE_FILE" down
        docker volume rm bpp_certbot-etc bpp_certbot-var bpp_web-root 2>/dev/null || true
        print_message "$GREEN" "Czyszczenie zakończone"
    else
        print_message "$YELLOW" "Czyszczenie anulowane"
    fi
}

# Main menu
show_menu() {
    echo
    print_message "$YELLOW" "Narzędzie konfiguracji SSL dla BPP"
    echo "===================================="
    echo "1. Początkowa konfiguracja (pobierz certyfikaty i uruchom)"
    echo "2. Uruchom/Restartuj usługi"
    echo "3. Odnów certyfikaty"
    echo "4. Pokaż status certyfikatów"
    echo "5. Test z certyfikatami staging"
    echo "6. Wyczyść (usuń certyfikaty)"
    echo "7. Wyjście"
    echo
    read -r -p "Wybierz opcję: " choice

    case $choice in
        1)
            check_prerequisites
            if [ "$(check_certificates)" = "EXISTS" ]; then
                print_message "$YELLOW" "Certyfikaty już istnieją. Uruchamianie usług..."
                start_stack
            else
                obtain_certificates && start_stack
            fi
            ;;
        2)
            check_prerequisites
            start_stack
            ;;
        3)
            check_prerequisites
            renew_certificates
            ;;
        4)
            show_status
            ;;
        5)
            check_prerequisites
            test_staging
            ;;
        6)
            cleanup
            ;;
        7)
            print_message "$GREEN" "Do widzenia!"
            exit 0
            ;;
        *)
            print_message "$RED" "Nieprawidłowa opcja"
            ;;
    esac
}

# Main loop
while true; do
    show_menu
done
