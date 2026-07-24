Normalizacja danych osobowych autora z PBN (``lastName``/``familyName`` oraz
``firstName``/``givenNames``/``name``) korzysta teraz z ``pbn_client.normalize_author_name``
— jedno źródło prawdy dla niespójnych kształtów PBN, obejmujące także pole
``familyName``, którego wcześniejsza normalizacja rekordu PBN nie rozpoznawała.
