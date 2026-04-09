from django import forms
from django.contrib import admin
from django.forms.widgets import Textarea

from bpp.models import Uczelnia

from .models import Article

SmallerTextarea = Textarea(attrs={"cols": 75, "rows": 2})
BiggerTextarea = Textarea(attrs={"cols": 75, "rows": 18})


class ArticleForm(forms.ModelForm):
    class Meta:
        fields = [
            "title",
            "article_body",
            "status",
            "published_on",
            "slug",
            "uczelnie",
        ]
        model = Article
        widgets = {"title": SmallerTextarea, "article_body": BiggerTextarea}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    search_fields = ["title", "article_body"]
    list_display = ["title", "status", "created", "published_on"]
    list_filter = ["status", "uczelnie"]
    form = ArticleForm
    filter_horizontal = ["uczelnie"]
    prepopulated_fields = {"slug": ("title",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # New articles with no uczelnie selected → assign to all
        if not change and not obj.uczelnie.exists():
            obj.uczelnie.set(Uczelnia.objects.all())
