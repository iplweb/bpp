Naprawiono błąd 500 (NoReverseMatch) w API REST dla ``/api/v1/praca_doktorska/``
oraz ``/api/v1/praca_habilitacyjna/``, gdy rekord miał ustawionego wydawcę —
pole ``wydawca`` generowało hiperłącze bez przestrzeni nazw ``api_v1:``.
