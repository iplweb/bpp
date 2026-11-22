# Kompilator motywów konfiguratora wyglądu — osobny, odizolowany serwis
# (opis: docker/motyw-kompilator/serwer.js, docs/superpowers/specs/
# 2026-11-22-konfigurator-wygladu-design.md).
#
# Pliki JS i źródła SCSS bierzemy z obrazu bazowego TEJ SAMEJ wersji
# (`/app/staticroot.baked` — wynik grunt build + collectstatic), więc
# kompilator zawsze pasuje do appservera. Sam obraz: Node bez zależności npm.
ARG BPP_BASE_TAG=latest
ARG NODE_VERSION=22
FROM iplweb/bpp_base:${BPP_BASE_TAG} AS bpp

FROM node:${NODE_VERSION}-alpine

WORKDIR /app
COPY --from=bpp /app/staticroot.baked/bpp/js/motyw-konfig.js \
                /app/staticroot.baked/bpp/js/motyw-kompilator.js \
                /app/js/
COPY --from=bpp /app/staticroot.baked/bpp/js/dist/sass-przegladarka.js \
                /app/staticroot.baked/bpp/js/dist/motyw-zrodla-scss.json \
                /app/dist/
COPY docker/motyw-kompilator/serwer.js /app/serwer.js

ENV BPP_MOTYW_JS=/app/js \
    BPP_MOTYW_DIST=/app/dist \
    PORT=8095 \
    NODE_ENV=production

# Bez roota; pliki tylko do odczytu (kontener w bpp-deploy: read_only).
USER node
EXPOSE 8095

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8095/zdrowie || exit 1

CMD ["node", "/app/serwer.js"]
