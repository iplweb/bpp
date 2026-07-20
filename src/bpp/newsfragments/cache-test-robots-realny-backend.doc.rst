Test rozdzielności cache'a per-host dla ``robots.txt`` biegnie teraz na
realnym backendzie (``LocMemCache``) zamiast na wyłączonym ``DummyCache``.
Wcześniej przechodził trywialnie — nie dowodził, że ``cache_page`` nie
przecieka między domenami multi-hosted. Dołożono warunek kontrolny
(trafienie w cache przy powtórzonym żądaniu), który realnie pada, gdy
cache przestaje działać.
