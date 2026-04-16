Usunięto mechanizm automatycznych offsetów portów per-worktree: skrypt
``bin/prepare-worktree.sh``, targety ``make new-worktree`` /
``make clean-worktree`` oraz sekcję „Docker exposed ports (with worktree
offset)” w ``.env.example``. Równoległa izolacja testów jest realizowana
przez ``testcontainers_bpp`` (losowe porty), więc dev-stack może
spokojnie jeździć na jednej kopii usług na maszynę na domyślnych
portach (``5432`` / ``6379`` / ``5672`` / ``8000`` …).
