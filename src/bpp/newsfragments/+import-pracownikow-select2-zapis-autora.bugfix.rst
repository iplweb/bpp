W podglądzie importu pracowników zmiana autora przez wyszukiwarkę Select2
(„dopasuj do istniejącego autora” / „inny autor”) znów się zapisuje.
Wcześniej wybór nie zapisywał się nigdzie — Select2 emituje zdarzenie
``change`` przez jQuery, którego natywny listener htmx nie łapał, więc żądanie
zapisu nie wychodziło. Dodano mostek zdarzenia (``select2:select`` →
natywny ``change``).
