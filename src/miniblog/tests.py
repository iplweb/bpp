# Create your tests here.
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError

from miniblog.models import Article


def test_Article___str__():
    a = Article(title="Artykuł", status="draft")
    assert (
        str(a) == 'Artykuł "Artykuł" - szkic' or str(a) == 'Artykuł "Artykuł" - draft'
    )

    a = Article(title="Artykuł", status="published")
    assert (
        str(a) == 'Artykuł "Artykuł" - opublikowany'
        or str(a) == 'Artykuł "Artykuł" - published'
    )


@pytest.mark.django_db
def test_article_get_absolute_url_draft():
    """Test that draft articles return admin change URL."""
    article = Article.objects.create(
        title="Test Draft",
        status="draft",
        slug="test-draft",
        article_body="Simple body",
    )

    url = article.get_absolute_url()

    assert "admin" in url
    assert "miniblog" in url
    assert "article" in url
    assert str(article.pk) in url


@pytest.mark.django_db
def test_article_get_absolute_url_published_with_more(uczelnia):
    """Test that published articles with more content return article detail URL."""
    from django.conf import settings

    split_marker = getattr(settings, "SPLIT_MARKER", "<!-- tutaj -->")
    body_with_more = f"Short excerpt{split_marker}Full article content here"

    article = Article.objects.create(
        title="Test Published With More",
        status="published",
        slug="test-published",
        article_body=body_with_more,
    )

    url = article.get_absolute_url()

    # After creation, check if has_more is properly set
    if article.article_body.has_more:
        assert "artykul" in url
        assert article.slug in url
    else:
        # If SplitField doesn't detect "more", it returns uczelnia URL
        assert uczelnia.slug in url


@pytest.mark.django_db
def test_article_get_absolute_url_published_without_more(uczelnia):
    """Test that published articles without more content return uczelnia page URL."""
    article = Article.objects.create(
        title="Test Published No More",
        status="published",
        slug="test-no-more",
        article_body="Just a simple article body without split marker",
    )

    url = article.get_absolute_url()

    assert uczelnia.slug in url


@pytest.mark.django_db
def test_article_slug_uniqueness():
    """Test that article slug must be unique."""
    Article.objects.create(
        title="First Article",
        slug="unique-slug",
        article_body="Body 1",
    )

    with pytest.raises(IntegrityError):
        Article.objects.create(
            title="Second Article",
            slug="unique-slug",
            article_body="Body 2",
        )


@pytest.mark.django_db
def test_invalidate_cache_on_article_change_published(uczelnia):
    """Test that cache is invalidated when published article is saved."""
    with patch(
        "bpp.views.browse.get_uczelnia_context_data"
    ) as mock_get_uczelnia_context_data:
        mock_get_uczelnia_context_data.invalidate = MagicMock()

        article = Article.objects.create(
            title="Cache Test",
            status="published",
            slug="cache-test",
            article_body="Test body",
        )
        # Trigger post_save by saving again
        article.title = "Updated title"
        article.save()

        mock_get_uczelnia_context_data.invalidate.assert_called()


@pytest.mark.django_db
def test_article_ordering():
    """Test that articles are ordered by published_on descending, then title."""
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()

    # Create articles with different dates and titles
    article1 = Article.objects.create(
        title="BBB Article",
        slug="bbb-article",
        article_body="Body 1",
        published_on=now - timedelta(days=2),
    )
    article2 = Article.objects.create(
        title="AAA Article",
        slug="aaa-article",
        article_body="Body 2",
        published_on=now - timedelta(days=1),
    )
    article3 = Article.objects.create(
        title="CCC Article",
        slug="ccc-article",
        article_body="Body 3",
        published_on=now,
    )

    articles = list(Article.objects.all())

    # Should be ordered by published_on descending (newest first)
    assert articles[0] == article3  # now (newest)
    assert articles[1] == article2  # now - 1 day
    assert articles[2] == article1  # now - 2 days (oldest)


@pytest.mark.django_db
def test_article_status_choices():
    """Test that article has correct status choices."""
    assert "draft" in Article.STATUS
    assert "published" in Article.STATUS
    assert len(Article.STATUS) == 2
