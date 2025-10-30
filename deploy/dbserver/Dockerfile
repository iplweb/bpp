#check=skip=SecretsUsedInArgOrEnv
FROM postgres:16.3

RUN localedef -i pl_PL -c -f UTF-8 -A /usr/share/locale/locale.alias pl_PL.UTF-8

ENV LANG=pl_PL.utf-8
ENV POSTGRES_INITDB_ARGS="--locale-provider=icu --icu-locale=pl-PL"
ENV POSTGRES_HOST_AUTH_METHOD=trust

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD pg_isready -U postgres

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update && apt install -y postgresql-plpython3-16 python-is-python3

COPY --chmod=755 autotune.py /
COPY --chmod=755 docker-entrypoint-autotune.sh /usr/local/bin/

ENTRYPOINT ["docker-entrypoint-autotune.sh"]

CMD ["postgres"]
