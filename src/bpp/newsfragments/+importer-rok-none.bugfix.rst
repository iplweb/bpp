Importer publikacji wywalał się z ``TypeError: '>' not supported between
instances of 'NoneType' and 'int'`` przy próbie utworzenia rekordu, gdy
dane źródłowe (np. BibTeX) nie zawierały roku publikacji. Po stronie
``ISlot`` dodano obsługę ``rok=None`` (zwracane jest ``CannotAdapt``,
sloty nie są liczone), a w samym imporcie ``_create_publication``
waliduje obecność roku i zgłasza czytelny komunikat zamiast pełnego
tracebacku.
