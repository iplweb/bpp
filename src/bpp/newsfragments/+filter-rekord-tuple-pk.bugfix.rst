Naprawiono ``Autorzy.objects.filter_rekord()`` wywoływane z rekordem
pobranym z bazy: klucz główny z ``TupleField`` (tuple) trafiał w ścieżkę
lookupów wielokolumnowych FK i kończył się błędem PostgreSQL „operator
nie istnieje: integer[] = integer". Manager normalizuje teraz tuple do
listy.
