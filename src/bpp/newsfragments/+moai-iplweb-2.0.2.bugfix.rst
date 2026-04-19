Podniesiono zależność ``MOAI-iplweb`` do 2.0.2. Nowa wersja forka
zastępuje przestarzałe ``pkg_resources`` (``iter_entry_points``,
``working_set``) przez standardowe ``importlib.metadata`` — eliminuje
16 ostrzeżeń ``DeprecationWarning: pkg_resources is deprecated as an
API`` pojawiających się przy uruchamianiu testów i zbieraniu pluginów
OAI.
