# Create your tests here.
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
