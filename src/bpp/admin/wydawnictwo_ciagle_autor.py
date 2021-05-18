# -*- encoding: utf-8 -*-


from django.contrib import admin

from bpp.admin.wydawnictwo_autor_base import Wydawnictwo_Autor_Base
from bpp.models import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor


@admin.register(Wydawnictwo_Ciagle_Autor)
class Wydawnictwo_Ciagle_Autor_Admin(Wydawnictwo_Autor_Base):
    klasa_autora = Wydawnictwo_Ciagle_Autor
    base_rekord_class = Wydawnictwo_Ciagle
    change_list_template = "admin/bpp/wydawnictwo_ciagle_autor/change_list.html"
