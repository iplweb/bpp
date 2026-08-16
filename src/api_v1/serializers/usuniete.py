from rest_framework import serializers


class UsunietySerializer(serializers.Serializer):
    """Nagrobek: co zniknęło i kiedy — NIGDY treść rekordu.

    Świadomie ``Serializer``, nie ``ModelSerializer``: łączymy wiele modeli
    w jedną listę, a każde pole ponad te trzy byłoby wyciekiem danych,
    które redakcja usunęła.
    """

    model = serializers.CharField()
    pk = serializers.IntegerField()
    usuniety_od = serializers.DateTimeField()
