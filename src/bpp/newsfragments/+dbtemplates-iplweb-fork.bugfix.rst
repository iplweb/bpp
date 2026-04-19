Zamieniono zależność ``django-dbtemplates`` na utrzymywany przez IPLweb
fork ``django-dbtemplates-iplweb`` (>=4.3.2). Fork używa
``importlib.metadata`` zamiast przestarzałego ``pkg_resources``, co
likwiduje ``DeprecationWarning: pkg_resources is deprecated as an API``
podczas uruchamiania testów i serwera. Nazwa importu (``dbtemplates``)
nie zmienia się — kod aplikacji nie wymaga modyfikacji.
