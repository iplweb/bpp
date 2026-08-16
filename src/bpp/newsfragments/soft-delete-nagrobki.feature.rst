Repozytorium OAI-PMH ogłasza teraz usunięcia: rekord, który przestał być
eksportowany, wychodzi w harveście jako nagrobek (nagłówek ze statusem
``deleted``) zamiast po prostu zniknąć. Dzięki temu systemy pobierające dane
przyrostowo mogą usunąć go u siebie. Nowy endpoint ``/api/v1/usuniete/``
udostępnia listę usuniętych rekordów — wyłącznie identyfikator i datę,
bez treści.
