from django.conf import settings
from django.db import models

from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _
# Create your models here.
from model_utils.choices import Choices
from model_utils.fields import SplitField
from model_utils.models import StatusModel, TimeStampedModel

SPLIT_MARKER = getattr(settings, "SPLIT_MARKER", "WTF")


class Article(TimeStampedModel, StatusModel):
    STATUS = Choices(('draft', _('draft')), ('published', _('published')))

    title = models.TextField(verbose_name=_("Title"))
    article_body = SplitField(
        verbose_name=_("Article body"),
        help_text=_('Use the split marker "%s" in case you want to display'
                    'the shorter version of the article body') % escape(
            SPLIT_MARKER))
    published_on = models.DateTimeField(
        verbose_name=_("Published on"),
        default=timezone.now)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = _("Articles")
        verbose_name = _("Article")
        ordering = ('-published_on', 'title')
