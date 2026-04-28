from django import forms
from django.contrib import admin
from django.forms.widgets import Textarea

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
