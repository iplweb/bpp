Naprawiono dwa błędy serializerów API: w ``PatentSerializer`` pole
``autorzy_set`` linkowało do ``wydawnictwo_zwarte_autor-detail`` zamiast do
``patent_autor-detail`` (błędny adres autorów patentu); w
``Praca_HabilitacyjnaSerializer`` pole ``publikacja_habilitacyjna`` było gołym
``serializers.RelatedField`` (brak ``to_representation`` → 500 przy powiązanej
publikacji) — zastąpione ``StringRelatedField`` po właściwej relacji odwrotnej.
