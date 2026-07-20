CI: testy przeglądarkowe (Playwright) są ponawiane raz przy porażce
(``pytest-rerunfailures``), a pull obrazów Docker (``iplweb/bpp_dbserver``,
``redis``, test-runner) ma retry z backoffem. Redukuje szum CI z flake'ów
Playwrighta i timeoutów rejestru, nie maskując przy tym niedeterminizmu w
testach jednostkowych — retry jest zawężony wyłącznie do testów z markerem
``playwright``.
