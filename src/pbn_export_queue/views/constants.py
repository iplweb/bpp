"""Constants and templates for PBN export queue views."""

# Email template for PBN helpdesk error reporting
HELPDESK_EMAIL_TEMPLATE = """Temat: Błąd eksportu do PBN - {record_title_short}
Do: pomoc@pbn.nauka.gov.pl
Od: {user_email}

Dzień dobry,

Zwracam się z prośbą o pomoc w rozwiązaniu problemu z eksportem publikacji do systemu PBN.

SZCZEGÓŁY BŁĘDU:
- Data i godzina wysyłki: {submitted_date}
- Kod błędu HTTP: {error_code}
- Endpoint API: {error_endpoint}
- Tytuł publikacji: {record_title}

ODPOWIEDŹ Z API PBN:
{error_details}

KONTEKST:
Próbowaliśmy wysłać publikację do systemu PBN, jednak otrzymaliśmy błąd. Nie mamy pewności, \
co jest przyczyną problemu i prosimy o pomoc Helpdesku PBN w zidentyfikowaniu przyczyny \
oraz wskazówki, jak poprawić dane.

DANE TECHNICZNE:
- ID kolejki eksportu: {queue_pk}
- Typ rekordu: {content_type}
- Ilość prób wysyłki: {ilosc_prob}

KOD JSON WYSŁANY DO PBN API:
{json_data}

Z poważaniem,
{user_name}
"""

# AI prompt template for analyzing PBN export errors
AI_PROMPT_TEMPLATE = """Proszę o pomoc w naprawieniu błędu eksportu publikacji do systemu \
PBN (Polski Narodowy Bibliografii).

# KONTEKST
Próbuję wysłać publikację do PBN API, ale otrzymuję błąd. Potrzebuję wskazówek, \
co jest nie tak z wysyłanymi danymi.

# DANE WYSŁANE DO PBN API
```json
{json_data}
```

# OTRZYMANY BŁĄD
- Kod HTTP: {error_code}
- Szczegóły błędu:
{error_details}
- Tytuł publikacji: {record_title}

# ZADANIE
Przeanalizuj wysłane dane JSON oraz otrzymany błąd i wskaż:
1. Co jest nie tak z danymi JSON zgodnie z dokumentacją API PBN?
2. Jakie pola są błędne lub brakujące?
3. Jak poprawić dane, aby eksport się powiódł?

# DOKUMENTACJA
Dokumentacja API PBN jest dostępna pod adresem: https://pbn.nauka.gov.pl/api/

Proszę o szczegółową analizę i konkretne wskazówki naprawcze.
"""
