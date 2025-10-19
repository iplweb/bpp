from datetime import datetime

from django.contrib import admin
from django.urls import reverse
from django.utils.http import urlencode

from bpp.admin.filters import OrcidObecnyFilter
from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import (
    OdpowiednikAutoraWBPPFilter,
    PbnIdObecnyFilter,
    PolonUidObecnyFilter,
)
from pbn_api.models import Scientist


@admin.register(Scientist)
class ScientistAdmin(BaseMongoDBAdmin):
    show_full_result_count = False
    list_display = [
        "lastName",
        "name",
        "qualifications",
        "polonUid",
        "orcid",
        "currentEmploymentsInstitutionDisplayName",
        "mongoId",
        "from_institution_api",
        "rekord_w_bpp",
    ]

    search_fields = [
        "mongoId",
        "lastName",
        "name",
        "orcid",
    ]

    fields = BaseMongoDBAdmin.fields + [
        "from_institution_api",
    ]
    readonly_fields = BaseMongoDBAdmin.readonly_fields + ["from_institution_api"]
    list_filter = [
        OdpowiednikAutoraWBPPFilter,
        OrcidObecnyFilter,
        PolonUidObecnyFilter,
        PbnIdObecnyFilter,
        "from_institution_api",
        "qualifications",
    ] + BaseMongoDBAdmin.list_filter

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Dodaje URL do utworzenia autora w BPP do kontekstu."""
        extra_context = extra_context or {}

        obj = self.get_object(request, object_id)
        if obj and not obj.rekord_w_bpp:
            # Przygotuj dane do utworzenia autora
            params = self._prepare_autor_params(obj)
            url = reverse("admin:bpp_autor_add") + "?" + urlencode(params)
            extra_context["create_in_bpp_url"] = url

        return super().change_view(request, object_id, form_url, extra_context)

    def _add_basic_autor_params(self, params, obj):
        """Add basic autor parameters (name, lastName, orcid, pbn_uid)."""
        if obj.name:
            params["imiona"] = obj.name
        if obj.lastName:
            params["nazwisko"] = obj.lastName
        if obj.orcid:
            params["orcid"] = obj.orcid
        params["pbn_uid"] = obj.pk

    def _add_tytul_param(self, params, obj):
        """Add tytul parameter if available."""
        tytul_id = self._get_tytul_id(obj.qualifications)
        if tytul_id:
            params["tytul"] = tytul_id

    def _add_employment_date_param(self, params, prefix, date_str):
        """Add employment date parameter with format conversion."""
        if not date_str:
            return
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            params[prefix] = date_obj.strftime("%Y-%m-%d")
        except BaseException:
            pass

    def _add_employment_params(self, params, employment_data):
        """Add employment data parameters."""
        if not employment_data or not employment_data.get("jednostka_id"):
            return

        params["autor_jednostka_set-0-jednostka"] = employment_data["jednostka_id"]
        self._add_employment_date_param(
            params, "autor_jednostka_set-0-rozpoczal_prace", employment_data.get("od")
        )
        self._add_employment_date_param(
            params, "autor_jednostka_set-0-zakonczyl_prace", employment_data.get("do")
        )
        params["autor_jednostka_set-TOTAL_FORMS"] = "1"
        params["autor_jednostka_set-INITIAL_FORMS"] = "0"
        params["autor_jednostka_set-MIN_NUM_FORMS"] = "0"
        params["autor_jednostka_set-MAX_NUM_FORMS"] = "1000"

    def _add_disciplines_params(self, params, disciplines):
        """Add disciplines parameters."""
        if not disciplines:
            return

        for i, disc_data in enumerate(disciplines[:2]):  # Maksymalnie 2 dyscypliny
            year = disc_data.get("year", datetime.now().year)
            params[f"autor_dyscyplina_set-{i}-rok"] = year
            if disc_data.get("dyscyplina_id"):
                params[f"autor_dyscyplina_set-{i}-dyscyplina_naukowa"] = disc_data[
                    "dyscyplina_id"
                ]
            if disc_data.get("procent"):
                params[f"autor_dyscyplina_set-{i}-procent_dyscypliny"] = disc_data[
                    "procent"
                ]

        params["autor_dyscyplina_set-TOTAL_FORMS"] = str(len(disciplines))
        params["autor_dyscyplina_set-INITIAL_FORMS"] = "0"
        params["autor_dyscyplina_set-MIN_NUM_FORMS"] = "0"
        params["autor_dyscyplina_set-MAX_NUM_FORMS"] = "1000"

    def _prepare_autor_params(self, obj):
        """Przygotowuje parametry do utworzenia autora w BPP."""
        params = {}

        self._add_basic_autor_params(params, obj)
        self._add_tytul_param(params, obj)

        employment_data = self._get_employment_data(obj)
        self._add_employment_params(params, employment_data)

        disciplines = self._get_disciplines(obj)
        self._add_disciplines_params(params, disciplines)

        return params

    def _get_tytul_id(self, qualifications):
        """Znajdź ID tytułu naukowego na podstawie kwalifikacji z PBN."""
        if not qualifications:
            return None

        from bpp.models import Tytul

        # Mapowanie popularnych tytułów
        mapping = {
            "prof. dr hab.": "prof. dr hab.",
            "prof.": "prof.",
            "dr hab.": "dr hab.",
            "dr": "dr",
            "mgr": "mgr",
            "mgr inż.": "mgr inż.",
            "inż.": "inż.",
            "lek.": "lek.",
        }

        qualifications_lower = qualifications.lower().strip()
        for key, value in mapping.items():
            if key in qualifications_lower:
                try:
                    tytul = Tytul.objects.get(skrot=value)
                    return tytul.pk
                except Tytul.DoesNotExist:
                    pass

        return None

    def _get_jednostka_by_institution_id(self, institution_id):
        """Get Jednostka by PBN institution ID."""
        from bpp.models import Jednostka

        if not institution_id:
            return None
        try:
            jednostka = Jednostka.objects.get(pbn_uid_id=institution_id)
            return jednostka.pk
        except Jednostka.DoesNotExist:
            return None

    def _process_current_employment(self, data, employment):
        """Process current employment data."""
        if "from" in employment:
            data["od"] = employment["from"]

        jednostka_id = self._get_jednostka_by_institution_id(
            employment.get("institutionId")
        )
        if jednostka_id:
            data["jednostka_id"] = jednostka_id

    def _process_archival_employment(self, data, latest_employment):
        """Process archival employment data."""
        if "from" in latest_employment and "od" not in data:
            data["od"] = latest_employment["from"]
        if "to" in latest_employment:
            data["do"] = latest_employment["to"]

        if "jednostka_id" not in data:
            jednostka_id = self._get_jednostka_by_institution_id(
                latest_employment.get("institutionId")
            )
            if jednostka_id:
                data["jednostka_id"] = jednostka_id

    def _get_employment_data(self, obj):
        """Pobierz dane o zatrudnieniu z current_version."""
        data = {}

        # Sprawdź currentEmployments
        current_employments = obj.value_or_none("object", "currentEmployments")
        if current_employments and len(current_employments) > 0:
            self._process_current_employment(data, current_employments[0])

        # Sprawdź archivalEmployments dla daty zakończenia
        archival_employments = obj.value_or_none("object", "archivalEmployments")
        if archival_employments and len(archival_employments) > 0:
            latest = sorted(
                archival_employments, key=lambda x: x.get("to", ""), reverse=True
            )[0]
            self._process_archival_employment(data, latest)

        return data

    def _get_disciplines(self, obj):
        """Pobierz informacje o dyscyplinach z PBN i zamień na BPP."""

        disciplines = []

        # Sprawdź currentEmployments
        current_employments = obj.value_or_none("object", "currentEmployments")
        if current_employments and len(current_employments) > 0:
            employment = current_employments[0]
            pbn_disciplines = employment.get("disciplines", [])

            for pbn_disc in pbn_disciplines:
                discipline_uuid = pbn_disc.get("disciplineUuid")
                start_date = pbn_disc.get("startDate")

                if discipline_uuid and start_date:
                    # Wyciągnij rok z startDate
                    try:
                        year = int(start_date.split("-")[0])
                    except (ValueError, IndexError):
                        year = datetime.now().year

                    # Znajdź PBN dyscyplinę na podstawie UUID
                    try:
                        from pbn_api.models import Discipline

                        found = False
                        for pbn_discipline in Discipline.objects.filter(
                            uuid=discipline_uuid
                        ):
                            if pbn_discipline.parent_group.is_current:
                                found = True
                                break

                        if not found:
                            # Jeżeli nie ma tego kodu dyscypliny w aktualnym słowniku, to pomiń
                            continue

                        # Użyj TlumaczDyscyplin aby znaleźć odpowiednią BPP dyscyplinę
                        bpp_dyscyplina = self._find_bpp_discipline_by_pbn_discipline(
                            pbn_discipline, year
                        )
                        if bpp_dyscyplina:
                            disciplines.append(
                                {
                                    "year": year,
                                    "dyscyplina_id": bpp_dyscyplina.pk,
                                    "procent": 100.0,  # Domyślnie 100%
                                }
                            )
                    except Exception:
                        # Jeśli nic nie zadziała, pomiń tę dyscyplinę
                        pass

        return disciplines

    def _find_bpp_discipline_by_pbn_discipline(self, pbn_discipline, year):
        """Znajdź BPP dyscyplinę na podstawie obiektu PBN Discipline używając TlumaczDyscyplin."""
        from pbn_api.models import TlumaczDyscyplin

        # Znajdź TlumaczDyscyplin który mapuje na tę PBN dyscyplinę
        field_name = None
        if year >= 2024:
            field_name = "pbn_2024_now"
        elif year >= 2022:
            field_name = "pbn_2022_2023"
        elif year >= 2017:
            field_name = "pbn_2017_2021"

        if field_name:
            try:
                tlumacz = TlumaczDyscyplin.objects.get(**{field_name: pbn_discipline})
                return tlumacz.dyscyplina_w_bpp
            except TlumaczDyscyplin.DoesNotExist:
                pass

        return None
