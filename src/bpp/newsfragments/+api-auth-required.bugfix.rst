Endpointy ``/bpp/api/upload-punktacja-zrodla/``,
``/bpp/api/punktacja-zrodla/``, ``/bpp/api/rok-habilitacji/``,
``/bpp/api/ostatnia-jednostka-i-dyscyplina/`` oraz
``/bpp/api/pubmed-id/`` wymagają teraz zalogowania.
Wcześniej były ``csrf_exempt`` bez sprawdzania
uwierzytelnienia — w szczególności
``upload-punktacja-zrodla`` przyjmował anonimowe POST-y
i tworzył wpisy ``Punktacja_Zrodla`` w bazie. Adminowy JS
nadal działa bez zmian (sesja zalogowanego użytkownika);
zmiana blokuje wyłącznie wywołania nieautoryzowane.
