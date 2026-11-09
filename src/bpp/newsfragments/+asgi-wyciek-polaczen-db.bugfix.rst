Naprawiono wyciek połączeń z bazą danych w serwerze aplikacji (ASGI).
Część kodu wykonywanego poza wątkiem żądania — m.in. strony błędów
404/500 oraz middleware ``easyaudit`` — otwierała połączenia, których
nikt nie zamykał; wisiały jako bezczynne aż do restartu procesu
i przy większym ruchu zapychały pulę ``pgbouncer``, co kończyło się
błędami „server closed the connection unexpectedly”. Usunięto
przestarzałą globalną podmianę ``sync_to_async``
(``thread_sensitive=False``), a połączenia otwarte w wątkach puli
pętli ASGI są teraz zamykane po każdym zadaniu.
