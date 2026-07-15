Bezpieczeństwo: nazwiska autorów pochodzące z importu (np. BibTeX) są teraz
escapowane przy wyświetlaniu w rankingu autorów oraz w panelu admina importera
publikacji — usunięto podatność stored XSS (surowa interpolacja do
``mark_safe()``/``safe()`` zastąpiona przez ``format_html``).
