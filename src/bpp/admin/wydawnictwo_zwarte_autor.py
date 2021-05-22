# -*- encoding: utf-8 -*-


from django.contrib import admin

from bpp.admin.wydawnictwo_autor_base import Wydawnictwo_Autor_Base
from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


@admin.register(Wydawnictwo_Zwarte_Autor)
class Wydawnictwo_Zwarte_Autor_Admin(Wydawnictwo_Autor_Base):
    klasa_autora = Wydawnictwo_Zwarte_Autor
    base_rekord_class = Wydawnictwo_Zwarte
    change_list_template = "admin/bpp/wydawnictwo_zwarte_autor/change_list.html"
