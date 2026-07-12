Bezpieczeństwo: importer publikacji z repozytorium DSpace nie pobiera już
danych z adresów wewnętrznych (loopback, sieci prywatne, endpointy metadata
chmury) — provider DSpace korzysta teraz z tej samej ochrony przed SSRF co
provider WWW (walidacja hosta i bezpieczne śledzenie przekierowań).
