Naprawiono problem z drukowaniem tabel z wyszukiwarki multiseek w przeglądarce
Edge (formaty "Tabela" oraz "tabela z punktacją wewnętrzną"). Przyczyną był
atrybut CSS ``overflow: hidden``, który powodował ukrycie zawartości podczas
drukowania w starszych wersjach Edge.
