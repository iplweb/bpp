Pliki statyczne są prekompresowane gzipem już w obrazie Dockera, a wyjście
django-compressora (``CACHE/``) przy starcie kontenera. Nginx w ``bpp-deploy``
ma ``gzip_static on`` włączone od dawna, ale bez plików ``.gz`` dyrektywa nic
nie robiła — każde żądanie kompresowało plik od nowa. Największe assety
(``plotly.min.js`` 4,4 MB, ``three-bundle.js`` 1,9 MB) schodzą teraz z dysku
gotowe, mocniej skompresowane (poziom 9 zamiast 5) i bez narzutu CPU na brzegu.
