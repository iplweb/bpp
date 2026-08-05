from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers

from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)

# Serializers define the API representation.


class RaportSlotowUczelniaSerializer(serializers.ModelSerializer):
    id = serializers.HyperlinkedRelatedField(
        view_name="api_v1:raport_slotow_uczelnia-detail", read_only=True
    )

    class Meta:
        model = RaportSlotowUczelnia
        read_only_fields = [
            "created_on",
            "started_on",
            "finished_on",
            "finished_successfully",
            "owner",
        ]
        fields = [
            "id",
            #
            # LiveOperation
            #
            # "owner",
            "created_on",
            "started_on",
            "finished_on",
            "finished_successfully",
            #
            # RaportSlotowUczelnia
            #
            "od_roku",
            "do_roku",
            "akcja",
            "slot",
            "minimalny_pk",
            "dziel_na_jednostki_i_wydzialy",
            "pokazuj_zerowych",
        ]

    def validate(self, attrs):
        if (
            attrs.get("akcja") == RaportSlotowUczelnia.Akcje.SLOTY
            and attrs.get("slot") is None
        ):
            raise ValidationError(
                {
                    "slot": "slot nie moze byc pusty dla akcji zbierania do wielkosci slotu"
                }
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # LOW-4: ścieżka API (druga obok widoku) NIE ustawia ``uczelnia`` —
        # raport z API jest nie-zawężony (wszystkie uczelnie). Owner-scope i
        # tak izoluje odczyt. To zachowanie OBECNE (przed migracją), świadomie
        # zachowane — patrz PR / plan §8.1.
        validated_data["owner"] = self.context["request"].user
        inst = super().create(validated_data)

        # create() jest @transaction.atomic — enqueue MUSI iść przez
        # on_commit, inaczej worker (celery) wystartowałby zanim wiersz się
        # zacommituje. liveops.enqueue() nie ma retry-loopa, więc bez tego
        # task nie znalazłby rekordu.
        transaction.on_commit(inst.enqueue)

        return inst


class RaportSlotowUczelniaWierszSerializer(serializers.ModelSerializer):
    parent = serializers.HyperlinkedRelatedField(
        view_name="api_v1:raport_slotow_uczelnia-detail", read_only=True
    )
    autor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )

    jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    dyscyplina = serializers.StringRelatedField()

    # pkd_aut_sum = serializers.DecimalField()
    # slot = serializers.DecimalField()
    # avg = serializers.DecimalField()

    class Meta:
        model = RaportSlotowUczelniaWiersz
        fields = [
            "parent",
            "autor",
            "jednostka",
            "dyscyplina",
            "pkd_aut_sum",
            "slot",
            "avg",
        ]
