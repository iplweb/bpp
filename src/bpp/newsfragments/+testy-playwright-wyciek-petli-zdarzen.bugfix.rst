Poprawiona stabilność testów ``import_pracownikow`` przy uruchamianiu
współbieżnym (pytest-xdist, sharding CI): testy Playwright (sync-API na
greenletach) potrafiły zostawić w wątku workera ustawiony ``asyncio``
running-loop marker, przez co kolejny test analizy importu na tym samym
workerze wywalał ``async_to_sync`` (eager-runner liveops →
``WebProgress`` → ``channel_layer.group_send``) na „You cannot use
AsyncToSync in the same thread as an async event loop". Wyjątek był
połykany przez runner, a stan importu utykał na ``zmapowany`` — flake
zależny od kolejności shardowania. Fixture izoluje teraz test od
wyciekłej pętli (zeruje marker na czas testu i przywraca go po nim).
