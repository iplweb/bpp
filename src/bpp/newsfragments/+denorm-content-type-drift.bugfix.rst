Triggery denormalizacji (``django-denorm-iplweb``, bump do ``1.12.1``)
rozwiązują teraz identyfikator typu treści (``content_type_id``)
dynamicznie w momencie zadziałania triggera, zamiast mieć go zaszytego
na stałe w treści triggera. Dzięki temu znikają błędy
``ForeignKeyViolation`` na tabeli ``denorm_dirtyinstance``, gdy
identyfikatory w ``django_content_type`` zmienią numerację po stronie
triggerów — np. po odtworzeniu bazy z innego zrzutu albo po przebudowie
typów treści. ``drop_triggers`` poprawnie usuwa też osierocone triggery
po wcześniejszych wersjach biblioteki (pełny ``drop`` + ``install``).
