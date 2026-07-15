Bezpieczeństwo: domknięto kilka wektorów XSS — komunikaty systemowe wstrzykiwane
do skryptu na stronie są escapowane dla kontekstu JavaScript, tytuł raportu
wyszukiwania („suggested-title") jest sanityzowany przy zapisie tak samo jak w
edytorze tytułu, a linki w panelach administracyjnych (m.in. deduplikator
autorów) budują etykiety przez ``format_html`` zamiast surowego ``mark_safe``.
