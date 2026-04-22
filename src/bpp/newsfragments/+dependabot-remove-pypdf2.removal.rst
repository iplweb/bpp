Usunięto nieużywaną zależność deweloperską ``PyPDF2`` z
``pyproject.toml``. Testy PDF korzystają z pakietu ``pypdf``,
który trafia do środowiska jako zależność tranzytywna
``xhtml2pdf``. ``PyPDF2`` jest nieutrzymywany i posiadał alert
bezpieczeństwa Dependabot bez dostępnej poprawki.
