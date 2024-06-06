FROM postgres:16.3

RUN localedef -i pl_PL -c -f UTF-8 -A /usr/share/locale/locale.alias pl_PL.UTF-8

ENV LANG pl_PL.utf-8
ENV POSTGRES_INITDB_ARGS "--locale-provider=icu --icu-locale=pl-PL"
ENV POSTGRES_HOST_AUTH_METHOD trust

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD pg_isready -U postgres

RUN apt update && apt install -y postgresql-plpython3-16 python-is-python3

COPY --chmod=755 autotune.py /
