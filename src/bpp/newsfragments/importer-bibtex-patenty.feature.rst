Importer publikacji: wklejony BibTeX ``@patent{...}`` jest teraz rozpoznawany
i parsowany (numer zgłoszenia, uprawniony, jurysdykcja, rodzaj prawa, data
zgłoszenia) zamiast lądować z pustym typem publikacji. Dodano
``_create_patent`` tworzące prawdziwy rekord ``bpp.Patent`` (z odfiltrowaniem
pól ``typ_kbn``/``charakter_formalny``, których ten model nie ma) oraz pole
``ImportSession.rodzaj_rekordu`` sterujące trójstronnym dispatchem
(ciągłe/zwarte/patent) — na razie dostępne programistycznie, wizard nie ma
jeszcze UI do wyboru "Patent" jako rodzaju rekordu ani kroku edycji pól
patentowych (osobna praca).

Przy okazji: formularz weryfikacji nie pozwala już wybrać "Patent" (ani
"Praca doktorska"/"Praca habilitacyjna") jako charakteru formalnego dla
wydawnictwa ciągłego/zwartego — wcześniej taki wybór tworzył zmieszany,
utykający w adminie rekord (importer omija ``full_clean()``, więc guard
``ZapobiegajNiewlasciwymCharakterom`` nigdy się nie odpalał).
