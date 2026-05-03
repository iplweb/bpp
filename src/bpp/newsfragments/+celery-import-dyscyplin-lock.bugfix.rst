Taski importu dyscyplin (``stworz_kolumny``,
``przeanalizuj_import_dyscyplin``,
``integruj_import_dyscyplin``) faktycznie ryglują rekord
``Import_Dyscyplin`` przez ``SELECT ... FOR UPDATE``.
Wcześniej wywołanie ``select_for_update().filter(pk=pk)``
zwracało leniwy ``QuerySet``, który nigdy nie był ewaluowany —
SQL z klauzulą ``FOR UPDATE`` nie szedł do bazy, a lock
realnie nie istniał. Przy równoczesnym przetwarzaniu tego
samego importu (np. user kliknie „Przeanalizuj” dwa razy
pod rząd) workery mogły deptać sobie po polach FSM.
