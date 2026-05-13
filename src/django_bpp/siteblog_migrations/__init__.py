# Override migrations for django-site-blog.
#
# django-site-blog 0.1.0 ships an 0001_initial generated against
# model-utils 4.x (uses SplitField(no_excerpt_field=True) which raises
# TypeError on model-utils 5). We override the whole migration tree
# here so it works with model-utils 5.x.
#
# Activated via MIGRATION_MODULES = {"siteblog": "django_bpp.siteblog_migrations"}
# in django_bpp/settings/base.py.
#
# Drop this once siteblog 0.1.1+ ships a 5.x-compatible migration:
# upstream issue https://github.com/iplweb/django-site-blog/issues/
