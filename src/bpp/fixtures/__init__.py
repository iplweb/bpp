# -*- encoding: utf-8 -*-


DANE_OPEN_ACCESS = """Wersja_Tekstu_OpenAccess	ORIGINAL_AUTHOR	Oryginalna wersja autorska
Wersja_Tekstu_OpenAccess	FINAL_AUTHOR	Ostateczna wersja autorska
Wersja_Tekstu_OpenAccess	FINAL_PUBLISHED	Ostateczna wersja opublikowana
Licencja_OpenAccess	CC-BY	Creative Commons - Uznanie Autorstwa (CC-BY)
Licencja_OpenAccess	CC-BY-SA	Creative Commons - Uznanie Autorstwa - Na Tych Samych Warunkach (CC-BY-SA)
Licencja_OpenAccess	CC-BY-NC	Creative Commons - Uznanie Autorstwa - Użycie niekomercyjne (CC-BY-NC);
Licencja_OpenAccess	CC-BY-ND	Creative Commons - Uznanie Autorstwa - Bez utworów zależnych (CC-BY-ND)
Licencja_OpenAccess	CC-BY-NC-SA	Creative Commons - Uznanie Autorstwa - Użycie niekomercyjne - Na tych samych warunkach (CC-BY-NC-SA)
Licencja_OpenAccess	CC-BY-NC-ND	Creative Commons - Uznanie Autorstwa - Użycie niekomercyjne - Bez utworów zależnych (CC-BY-NC-ND)
Licencja_OpenAccess	OTHER	inna otwarta licencja
Czas_Udostepnienia_OpenAccess	BEFORE_PUBLICATION	przed opublikowaniem
Czas_Udostepnienia_OpenAccess	AT_PUBLICATION	w momencie opublikowania
Czas_Udostepnienia_OpenAccess	AFTER_PUBLICATION	po opublikowaniu
Tryb_OpenAccess_Wydawnictwo_Ciagle	OPEN_JOURNAL	Otwarte czasopismo
Tryb_OpenAccess_Wydawnictwo_Ciagle	OPEN_REPOSITORY	Otwarte repositorium
Tryb_OpenAccess_Wydawnictwo_Ciagle	OTHER	Inne
Tryb_OpenAccess_Wydawnictwo_Zwarte	PUBLISHER_WEBSITE	Witryna wydawcy
Tryb_OpenAccess_Wydawnictwo_Zwarte	OPEN_REPOSITORY	Otwarte repositorium
Tryb_OpenAccess_Wydawnictwo_Zwarte	OTHER	Inne"""

def get_openaccess_data():
    for model_name, skrot, nazwa in [x.split('\t') for x in DANE_OPEN_ACCESS.split("\n")]:
        yield model_name.lower(), skrot, nazwa
