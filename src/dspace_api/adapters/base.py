class BaseDSpaceAdapter:
    """Bazowy adapter: rekord BPP → słownik metadanych Dublin Core."""

    dc_type = None

    def __init__(self, rec, domyslny_jezyk="pl"):
        self.rec = rec
        self.domyslny_jezyk = domyslny_jezyk

    def _val(self, value, language=None):
        return [
            {
                "value": value,
                "language": language,
                "authority": None,
                "confidence": -1,
            }
        ]

    def _multi(self, values, language=None):
        return [
            {
                "value": v,
                "language": language,
                "authority": None,
                "confidence": -1,
            }
            for v in values
        ]

    def _streszczenie(self):
        rec = self.rec
        bezposrednie = getattr(rec, "streszczenie", "")
        if bezposrednie:
            return bezposrednie
        # Rekordy BPP (Ciagle/Zwarte) trzymają streszczenia w powiązanej
        # kolekcji `streszczenia` (po jednym per język) — bierzemy pierwsze
        # niepuste.
        streszczenia = getattr(rec, "streszczenia", None)
        if streszczenia is not None and hasattr(streszczenia, "all"):
            for s in streszczenia.all():
                tekst = getattr(s, "streszczenie", "")
                if tekst:
                    return tekst
        return ""

    def _jezyk_iso(self):
        jezyk = getattr(self.rec, "jezyk", None)
        if jezyk and getattr(jezyk, "skrot", ""):
            return jezyk.skrot
        return self.domyslny_jezyk

    def _autorzy_wg_typu(self, skrot_typu):
        wynik = []
        qs = self.rec.autorzy_set.select_related(
            "autor", "typ_odpowiedzialnosci"
        ).order_by("kolejnosc")
        for p in qs:
            typ = getattr(p.typ_odpowiedzialnosci, "skrot", "")
            if skrot_typu is None or typ == skrot_typu:
                wynik.append(f"{p.autor.nazwisko}, {p.autor.imiona}")
        return wynik

    def common_dict(self):
        rec = self.rec
        d = {}
        if getattr(rec, "tytul_oryginalny", ""):
            d["dc.title"] = self._val(rec.tytul_oryginalny)
        if getattr(rec, "rok", None):
            d["dc.date.issued"] = self._val(str(rec.rok))
        streszczenie = self._streszczenie()
        if streszczenie:
            d["dc.description.abstract"] = self._val(streszczenie)
        if getattr(rec, "doi", ""):
            d["dc.identifier.doi"] = self._val(rec.doi)
        d["dc.language.iso"] = self._val(self._jezyk_iso())
        if self.dc_type:
            d["dc.type"] = self._val(self.dc_type)
        slowa = []
        if getattr(rec, "slowa_kluczowe", None) is not None:
            slowa += [t.name for t in rec.slowa_kluczowe.all()]
        eng = getattr(rec, "slowa_kluczowe_eng", None) or []
        slowa += list(eng)
        if slowa:
            d["dc.subject"] = self._multi(slowa)
        return d

    def to_dspace_dict(self):
        raise NotImplementedError
