from django.conf import settings
from django.db import models
from django.urls.base import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _

# Create your models here.
from model_utils.choices import Choices
from model_utils.fields import SplitField
from model_utils.models import StatusModel, TimeStampedModel

from bpp.models.struktura import Uczelnia

SPLIT_MARKER = getattr(settings, "SPLIT_MARKER", "WTF")


class Article(TimeStampedModel, StatusModel):
    STATUS = Choices(("draft", _("draft")), ("published", _("published")))

    title = models.TextField(verbose_name=_("Title"))
    article_body = SplitField(
        verbose_name=_("Article body"),
        help_text=_(
            'Use the split marker "%s" in case you want to display'
            "the shorter version of the article body"
        )
        % escape(SPLIT_MARKER),
    )
    published_on = models.DateTimeField(
        verbose_name=_("Published on"), default=timezone.now
    )
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = _("Articles")
        verbose_name = _("Article")
        ordering = ("-published_on", "title")

    def get_absolute_url(self):
        if self.status != self.STATUS.published:
            return reverse("admin:miniblog_article_change", args=(self.pk,))
        # TODO: co gdy będzie wiele uczelni w systemie?
        uczelnia = Uczelnia.objects.all().first()
        if self.article_body.has_more:
            return reverse("bpp:browse_artykul", args=(uczelnia.slug, self.slug))
        return reverse("bpp:browse_uczelnia", args=(uczelnia.slug,))

    def __str__(self):
        return f'Artykuł "{self.title}" - {self.STATUS[self.status]}'
