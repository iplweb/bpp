Przypięto wersję ``uv`` we wszystkich workflow-ach CI (``setup-uv`` bez
``version`` brał „latest", przez co gate ``uv.lock in sync`` potrafił
zaświecić się na czerwono na gałęzi, która nie ruszała zależności —
ten sam lockfile przechodził na uv 0.11.29, a padał na 0.11.31).
