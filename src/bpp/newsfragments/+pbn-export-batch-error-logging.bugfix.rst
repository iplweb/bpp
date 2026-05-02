Batchowe enqueueowanie do PBN
(``queue_pbn_export_batch``) raportuje teraz nieoczekiwane
błędy do Rollbara i logów zamiast cicho je połykać.
Wcześniej blok ``except Exception: pass`` w pętli po
rekordach pochłaniał wszystkie wyjątki (DB error,
integrity error, programmer error) — pojedynczy zły
rekord nie zatrzymywał batcha, ale operator nie miał
żadnej widoczności co poszło nie tak. Brakujące rekordy
(``DoesNotExist``) i już-w-kolejce
(``AlreadyEnqueuedError``) nadal są pomijane bez alertu —
to nie są błędy.
