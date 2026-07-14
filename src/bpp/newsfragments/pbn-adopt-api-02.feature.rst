BPP adoptuje API paczek PBN w wersji 0.2: property ``is_deleted`` zamiast
magic-stringa ``status == "DELETED"`` w modelach PBN, ``is_valid_object_id``
z ``pbn_client`` jako implementacja ``check_mongoId`` oraz
``get_or_download`` z ``django_pbn_client`` w funkcjach ``ensure_*``
integratora — usuwając zduplikowany kod przy zachowaniu identycznego
zachowania.
