Naprawiono migrację ``0413_bppuser_autor_onetoone``, która kończyła
się błędem ``cannot ALTER TABLE "bpp_bppuser" because it has pending
trigger events`` na bazach z istniejącymi danymi. Migracja została
oznaczona jako nieatomowa, dzięki czemu deferred triggery (``denorm``)
odpalane przez ``RunPython`` wystrzeliwują przed kolejnymi
``ALTER TABLE`` na tej samej tabeli.
