"""Okresy pracy autora w jednostce w formsetach admina (FD#640, BPP-1A).

Okresy pracy tego samego autora w tej samej jednostce nie mogą się nakładać
(constraint ``bpp_autor_jednostka_okresy_bez_nakladan``, natychmiastowy —
sprawdzany po każdej instrukcji SQL). Bez tego mixina naruszenie kończyło się
błędem 500 i przepadała cała edycja autora (np. usunięcie dyscypliny).
"""

from django.core.exceptions import ValidationError

from bpp.models import Autor_Jednostka

POLA_OKRESU = ("autor", "jednostka", "rozpoczal_prace", "zakonczyl_prace")


def _opis_okresu(od, do):
    koniec = f"do {do:%Y-%m-%d}" if do is not None else "bez daty zakończenia"
    return f"od {od:%Y-%m-%d} {koniec}"


class OkresyPracyFormSetMixin:
    """Dla inline formsetów ``Autor_Jednostka`` (w adminie autora i jednostki).

    - ``clean`` — nakładające się okresy to błąd formularza, nie 500.
      Walidacja modelu tego nie złapie: w formsecie inline pole klucza do
      rodzica jest wyłączone z walidacji, więc Django pomija constrainty,
      w których ono występuje, a nakładanie między dwoma NOWYMI wierszami i tak
      byłoby niewidoczne dla zapytania do bazy.
    - ``save_existing_objects`` — najpierw usuwa zaznaczone wiersze, potem
      zapisuje zmienione. Django robi to w jednej pętli w kolejności wierszy,
      więc np. scalenie okresów (usuń B, wydłuż A) najpierw wydłużało A, gdy
      B jeszcze było w bazie — i constraint wybuchał mimo poprawnego stanu
      końcowego.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        self._sprawdz_nakladanie_okresow()

    def _sprawdz_nakladanie_okresow(self):
        okresy = self._okresy_po_zapisie()
        for i, (autor, jednostka, od, do) in enumerate(okresy):
            for autor2, jednostka2, od2, do2 in okresy[i + 1 :]:
                if autor.pk != autor2.pk or jednostka.pk != jednostka2.pk:
                    continue
                # Przedziały domknięte, jak ``daterange(..., '[]')`` w bazie.
                if (do2 is None or od <= do2) and (do is None or od2 <= do):
                    raise ValidationError(
                        f"Okresy pracy autora {autor} w jednostce "
                        f"„{jednostka}” nakładają się ({_opis_okresu(od, do)} "
                        f"oraz {_opis_okresu(od2, do2)}). Przed dodaniem "
                        "nowego okresu uzupełnij datę zakończenia poprzedniego "
                        "(pole „Zakończył pracę”) albo popraw daty."
                    )

    def _okresy_po_zapisie(self):
        """Datowane okresy w stanie KOŃCOWYM: wiersze z formularza (bez
        zaznaczonych do usunięcia) plus wiersze z bazy, których formularz nie
        pokazuje (innej uczelni, ponad limit wierszy). Krotki
        (autor, jednostka, od, do). Pola tylko do odczytu bierzemy
        z instancji."""
        okresy = []
        pk_w_formularzu = set()
        for form in self.forms:
            if form.instance.pk is not None:
                pk_w_formularzu.add(form.instance.pk)
            cd = getattr(form, "cleaned_data", None) or {}
            if not cd or cd.get("DELETE"):
                continue
            okres = tuple(
                cd[pole] if pole in cd else getattr(form.instance, pole, None)
                for pole in POLA_OKRESU
            )
            if None not in okres[:3]:
                okresy.append(okres)

        if self.instance.pk is not None:
            z_bazy = (
                Autor_Jednostka.objects.filter(
                    **{self.fk.name: self.instance}, rozpoczal_prace__isnull=False
                )
                .exclude(pk__in=pk_w_formularzu)
                .select_related("autor", "jednostka")
            )
            okresy.extend(
                (aj.autor, aj.jednostka, aj.rozpoczal_prace, aj.zakonczyl_prace)
                for aj in z_bazy
            )
        return okresy

    def save_existing_objects(self, commit=True):
        # Kopia ``BaseModelFormSet.save_existing_objects`` z dwoma przebiegami:
        # najpierw usuwanie, potem zapis zmienionych (patrz docstring klasy).
        self.changed_objects = []
        self.deleted_objects = []
        if not self.initial_forms:
            return []

        forms_to_delete = self.deleted_forms
        istniejace = [
            form
            for form in self.initial_forms
            if form.instance._is_pk_set() and not form.instance._state.adding
        ]
        for form in istniejace:
            if form in forms_to_delete:
                self.deleted_objects.append(form.instance)
                self.delete_existing(form.instance, commit=commit)

        saved_instances = []
        for form in istniejace:
            if form in forms_to_delete or not form.has_changed():
                continue
            obj = form.instance
            self.changed_objects.append((obj, form.changed_data))
            saved_instances.append(self.save_existing(form, obj, commit=commit))
            if not commit:
                self.saved_forms.append(form)
        return saved_instances
