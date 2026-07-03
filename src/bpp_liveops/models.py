from liveops.models import LiveOperation


class BppLiveOperation(LiveOperation):
    """Cienka warstwa BPP nad ``liveops.LiveOperation``.

    Dokłada konwencje wspólne dla operacji BPP, których standardowy liveops
    nie ma (bo są specyficzne dla naszego wzorca importów z rekordami-dziećmi):

    - ``reset_children()`` — hook czyszczący rekordy potomne przy restarcie.
      Odpowiednik ``on_reset()`` ze starego ``long_running.models.Operation``.
      Standardowy ``liveops.views.RestartView`` resetuje tylko pola bazowe
      operacji i NIE wie o rekordach-dzieciach — dlatego ``BppRestartView``
      woła ten hook przed ponownym zakolejkowaniem.
    - ``readable_exception()`` — ostatnia niepusta linia tracebacku, do
      pokazania w szablonach (jak w starym ``Operation``).

    Klasa jest abstrakcyjna — nie tworzy własnej tabeli. Konkretne operacje
    (import list ministerialnych itd.) dziedziczą po niej i implementują
    ``run(self, p)``.
    """

    class Meta(LiveOperation.Meta):
        # Dziedziczymy po LiveOperation.Meta, żeby zachować ordering
        # (["-created_on"]); samo `class Meta: abstract=True` by je zgubiło.
        abstract = True

    def reset_children(self):
        """Wyczyść rekordy potomne przy restarcie operacji.

        Domyślnie no-op. Podklasy z rekordami-dziećmi (np. wiersze importu)
        nadpisują to, kasując swój ``*_set``.
        """

    def readable_exception(self):
        if not self.traceback:
            return None
        lines = [line for line in self.traceback.split("\n") if line]
        return lines[-1] if lines else None
