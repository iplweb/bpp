Zbumpowano ``django-denorm-iplweb`` z ``>=1.10.1`` do ``>=1.10.2``.
Release 1.10.2 dodaje ``get_joining_fields()`` do inline'owej
klasy ``JoinField`` w ``TriggerFilterQuery`` (``denorm/
denorms.py``), dzięki czemu Django 6.0 już nie emituje
``RemovedInDjango60Warning: The usage of get_joining_columns() in
Join is deprecated``.
