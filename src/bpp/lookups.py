from django.contrib.postgres.search import SearchQuery


class SearchQueryStartsWith(SearchQuery):
    def as_sql(self, compiler, connection):
        value = self.source_expressions[1].value
        params = [value]
        if self.config:
            config_sql, config_params = compiler.compile(self.config)
            template = f"to_tsquery({config_sql}::regconfig, %s)"
            params = config_params + [value]
        else:
            template = "to_tsquery(%s)"
        if self.invert:
            template = f"!!({template})"
        return template, params
