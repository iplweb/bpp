Strony ładują się szybciej: główny pakiet JavaScript (``bundle.js``)
schudł o ~600 KB (−39%) po usunięciu nieużywanej biblioteki Tone.js
(dźwięki powiadomień nigdy nie były włączone), a start kontenera nie
traci już czasu na ponowną minifikację zminifikowanego wcześniej
JavaScriptu (``COMPRESS_JS_FILTERS``).
