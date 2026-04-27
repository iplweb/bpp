<!-- Krótki tytuł powyżej; pełny opis poniżej. -->

## Co się zmienia

<!-- 1-3 zdania: co i dlaczego. -->

## Plan testowy

<!-- Checkbox listę: jak zweryfikować, że to działa (manualne kroki, testy, scenariusze). -->

- [ ]
- [ ]

## Checklist bezpieczeństwa

<!-- Wypełnij gdy dotyczy. Zob. docs/SECURITY_PRACTICES.md i SECURITY.md. -->

- [ ] Jeśli ten PR dodaje **nową zależność Pythona** — przeszedłem proces
      [Adding a new dependency](../docs/SECURITY_PRACTICES.md#adding-a-new-dependency)
      (Snyk DB / OSV check, maintainer count, last release age, attestacja
      Trusted Publisher).
- [ ] Jeśli dotyka **sekretów** lub `.env*` — żadne prawdziwe wartości w
      committed files (placeholders only). Zob.
      [Sekrety i .env](../docs/SECURITY_PRACTICES.md#sekrety-i-env).
- [ ] Jeśli dotyka **GitHub Actions workflowów** — zizmor w pre-commit
      przeszedł, akcje pinowane na SHA.
- [ ] Jeśli dotyka **Dockerfile** — nie wprowadza nowego `uv pip install`
      poza lockfile (poza świadomymi wyjątkami z docs/SECURITY_PRACTICES.md).

## Powiązane

<!-- Issue, ticket Freshdesk, poprzedni PR, etc. -->
