Uodporniono dwa testy na wymiecenie danych referencyjnych przez
transakcyjnego sąsiada (flaky na CI): test CrossRef API wylicza teraz
oczekiwany PK języka z klucza naturalnego zamiast go hardkodować, a test
kreatora pierwszego uruchomienia dostaje fixturą wiersz-singleton stanu
(``FirstRunWizardState``), bez którego middleware zwracał 302 zamiast 404.
