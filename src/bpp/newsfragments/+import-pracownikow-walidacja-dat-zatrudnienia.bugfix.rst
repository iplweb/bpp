Import pracowników: integracja odrzuca teraz odwrócony zakres dat zatrudnienia
(data rozpoczęcia późniejsza lub równa dacie zakończenia) zamiast po cichu
zapisywać go do bazy — ``Autor_Jednostka.clean()`` nie było wołane przy
``save()`` na ścieżce commitu.
