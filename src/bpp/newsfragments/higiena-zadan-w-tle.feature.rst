Higiena zadań w tle i retencji danych:

* długo działające zadania cykliczne (przeliczanie powiązań autorów, skan
  duplikatów autorów, automatyczna przebudowa cache dopasowań PBN) dostały
  limity czasu i blokadę pojedynczej instancji — zawieszone zadanie nie
  zablokuje już slotu workera na 6 godzin, a dwa równoległe przebiegi nie
  skasują sobie nawzajem wyników;
* przeliczanie powiązań autorów buduje wynik w tabeli tymczasowej i dopiero
  gotowy przepisuje do tabeli docelowej — czas, przez który tabela powiązań
  jest zablokowana dla zapisów, skrócił się z całego przeliczania do samego
  przepisania wierszy;
* dobowa przebudowa cache dopasowań PBN przesunięta z 3:30 na 4:30, żeby nie
  startowała równocześnie z porządkowaniem kolejności rekordów;
* nieudane próby logowania (django-axes) są kasowane po 90 dniach — dotąd
  wpisy generowane przez boty skanujące panel administracyjny zostawały
  w bazie bezterminowo;
* pliki XLS importu pracowników są wreszcie kasowane zgodnie z ustawioną
  retencją — komenda istniała, ale nic jej nie uruchamiało;
* naprawiono wpis harmonogramu czyszczenia kolejki eksportu do PBN, który
  wskazywał na nieistniejącą nazwę zadania i przez to nigdy się nie wykonywał.
