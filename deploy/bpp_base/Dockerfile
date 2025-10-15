##########################################################################################

FROM python:3.12-trixie AS builder

RUN pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# RUN --mount=type=cache,sharing=locked,target=/etc/apt/sources.list.d/  \
RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

# RUN --mount=type=cache,sharing=locked,target=/var/cache/apt  \
RUN apt update && \
    apt install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev curl gettext && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock yarn.lock package.json ./

RUN uv sync --frozen --all-extras --no-extra=dev --no-install-project

RUN npx yarn install --dev --ignore-optional

RUN npx yarn add grunt

COPY . .

RUN npx grunt build-non-interactive

RUN rm -rf node_modules

RUN npx yarn install --prod

# Comprehensive node_modules cleanup to reduce image size
RUN set -ex && \
    # Remove test files and directories \
    find /app/node_modules -type d \( \
        -name "test" -o -name "tests" -o -name "__tests__" \
        -o -name "spec" -o -name "specs" -o -name ".nyc_output" \
        -o -name "coverage" -o -name "test-fixtures" -o -name "fixture" \
        -o -name "fixtures" -o -name "benchmark" -o -name "benchmarks" \
    \) -exec rm -rf {} + 2>/dev/null || true && \
    find /app/node_modules -type f \( \
        -name "*.test.js" -o -name "*.spec.js" -o -name "*.test.ts" \
        -o -name "*.spec.ts" -o -name "test.js" -o -name "tests.js" \
    \) -delete 2>/dev/null || true && \
    # Remove documentation and example files \
    find /app/node_modules -type d \( \
        -name "docs" -o -name "doc" -o -name "documentation" \
        -o -name "example" -o -name "examples" -o -name "demo" \
        -o -name "demos" -o -name "samples" -o -name "sample" \
    \) -exec rm -rf {} + 2>/dev/null || true && \
    find /app/node_modules -type f \( \
        -name "*.md" -o -name "*.markdown" -o -name "*.rst" \
        -o -name "*.txt" -o -name "AUTHORS" -o -name "CONTRIBUTORS" \
        -o -name "PATENTS" -o -name "TODO" -o -name "CHANGELOG" \
        -o -name "CHANGES" -o -name "HISTORY" -o -name "NOTICE" \
        -o -name "SUMMARY" -o -name "USAGE" \
    \) ! -name "LICENSE*" ! -name "license*" ! -name "LICENCE*" -delete 2>/dev/null || true && \
    # Remove source maps and TypeScript sources \
    find /app/node_modules -type f \( \
        -name "*.map" -o -name "*.js.map" -o -name "*.css.map" \
    \) -delete 2>/dev/null || true && \
    find /app/node_modules -type f -name "*.ts" ! -name "*.d.ts" -delete 2>/dev/null || true && \
    find /app/node_modules -type f -name "*.tsx" -delete 2>/dev/null || true && \
    # Remove config and build files \
    find /app/node_modules -type f \( \
        -name ".npmignore" -o -name ".gitignore" -o -name ".gitattributes" \
        -o -name ".eslintrc*" -o -name ".eslintignore" -o -name ".prettierrc*" \
        -o -name ".prettierignore" -o -name ".babelrc*" -o -name ".travis.yml" \
        -o -name ".gitlab-ci.yml" -o -name "appveyor.yml" -o -name ".editorconfig" \
        -o -name "*.yml" -o -name "*.yaml" -o -name "tsconfig*.json" \
        -o -name "tslint.json" -o -name "jest.config.*" -o -name "karma.conf.*" \
        -o -name "webpack.config.*" -o -name "rollup.config.*" -o -name "Gruntfile.js" \
        -o -name "gulpfile.js" -o -name "Makefile" -o -name "Rakefile" \
        -o -name "bower.json" -o -name "composer.json" -o -name ".DS_Store" \
        -o -name "Thumbs.db" -o -name "*.log" \
    \) -delete 2>/dev/null || true && \
    # Remove source directories and build artifacts \
    find /app/node_modules -type d \( \
        -name "src" -o -name "source" -o -name "sources" \
        -o -name "build" -o -name ".github" -o -name ".circleci" \
        -o -name ".vscode" -o -name ".idea" \
    \) -exec rm -rf {} + 2>/dev/null || true && \
    # Remove C/C++ source files \
    find /app/node_modules -type f \( \
        -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.h" \
        -o -name "*.hpp" -o -name "*.gyp" -o -name "*.gypi" \
        -o -name "*.mk" -o -name "*.Makefile" -o -name "*.o" -o -name "*.a" \
    \) -delete 2>/dev/null || true && \
    # Remove lock files from dependencies \
    find /app/node_modules -type f \( \
        -name "package-lock.json" -o -name "yarn.lock" -o -name "pnpm-lock.yaml" \
    \) -delete 2>/dev/null || true && \
    # Remove images and media files \
    find /app/node_modules -type f \( \
        -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.gif" \
        -o -name "*.svg" -o -name "*.ico" -o -name "*.mp4" -o -name "*.webm" \
        -o -name "*.mp3" -o -name "*.wav" \
    \) -delete 2>/dev/null || true && \
    # Remove empty directories \
    find /app/node_modules -type d -empty -delete 2>/dev/null || true && \
    # Strip debug symbols from native binaries \
    find /app/node_modules -type f -name "*.node" -exec strip --strip-unneeded {} \; 2>/dev/null || true && \
    # Clean broken symlinks in .bin \
    find /app/node_modules/.bin -type l ! -exec test -e {} \; -delete 2>/dev/null || true && \
    echo "Node modules cleanup complete"

RUN uv run src/manage.py compilemessages -v0 --traceback

RUN uv cache clean

RUN uv cache prune

# Comprehensive cleanup to reduce image size (combined into fewer layers)
RUN set -ex && \
    # Remove Python bytecode and cache from both .venv and src \
    find /app -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete && \
    find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    # Remove test files and directories from .venv \
    find /app/.venv -type d \( -name "tests" -o -name "test" \) -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "test_*.py" -delete 2>/dev/null || true && \
    # Remove documentation from .venv \
    find /app/.venv -type d \( -name "docs" -o -name "doc" \) -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f \( -name "*.md" -o -name "*.rst" \) -delete && \
    # Remove type stubs \
    find /app/.venv -type f -name "*.pyi" -delete && \
    # Clean dist-info directories \
    find /app/.venv -type d -name "*.dist-info" -exec sh -c 'rm -rf "$1"/*.txt "$1"/*.rst "$1"/*.md "$1"/RECORD 2>/dev/null || true' _ {} \; && \
    # Remove unnecessary wheels \
    rm -rf /app/.venv/share/python-wheels 2>/dev/null || true && \
    # Strip .so files to reduce size further \
    find /app/.venv -type f -name "*.so" -exec strip --strip-unneeded {} \; 2>/dev/null || true && \
    # Clean up apt lists if any were created \
    rm -rf /var/lib/apt/lists/* && \
    # Report completion \
    echo "Cleanup complete"

##########################################################################################

FROM python:3.12-slim-trixie AS runtime

RUN sed -i s/http/https/g /etc/apt/sources.list.d/debian.sources

RUN pip install uv && \
    apt update && \
    apt install -y python3-pip libpango-1.0-0 libpangoft2-1.0-0 postgresql-client pandoc curl  && \
    apt-get clean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/.venv/bin:$PATH" \
    PYTHONPATH=/src \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules

COPY --from=builder /app/.venv ./.venv

COPY --from=builder /app/src ./src
