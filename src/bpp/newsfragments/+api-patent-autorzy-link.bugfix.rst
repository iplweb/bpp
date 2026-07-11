Naprawiono błąd w ``PatentSerializer`` API: pole ``autorzy_set`` linkowało do
``wydawnictwo_zwarte_autor-detail`` zamiast do ``patent_autor-detail``, przez co
odnośniki do autorów patentu prowadziły pod niewłaściwy adres. Teraz wskazują na
właściwy endpoint autorów patentu.
