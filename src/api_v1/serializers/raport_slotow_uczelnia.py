from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers

from long_running.tasks import perform_generic_long_running_task
from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)

from django.contrib.contenttypes.models import ContentType

# Serializers define the API representation.


class RaportSlotowUczelniaSerializer(serializers.ModelSerializer):
    id = serializers.HyperlinkedRelatedField(
        view_name="api_v1:raport_slotow_uczelnia-detail", read_only=True
    )

    class Meta:
        model = RaportSlotowUczelnia
        read_only_fields = [
            "created_on",
            "last_updated_on",
            "started_on",
            "finished_on",
            "finished_successfully",
            "owner",
        ]
        fields = [
            "id",
            #
            # Report
            #
            # "owner",
            "created_on",
            "last_updated_on",
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
        validated_data["owner"] = self.context["request"].user
        inst = super().create(validated_data)

        ct = ContentType.objects.get_for_model(inst)
        transaction.on_commit(
            lambda: perform_generic_long_running_task(ct.app_label, ct.model, inst.pk)
        )

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
