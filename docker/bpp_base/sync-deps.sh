#!/bin/sh
if [ "${BPP_SYNC_DEPS_ON_START:-0}" = "1" ]; then
    case "${DJANGO_SETTINGS_MODULE:-}" in
        *production*)
            echo "WARNING: BPP_SYNC_DEPS_ON_START=1 ignored — production settings detected" >&2
            ;;
        *)
            echo "Syncing Python dependencies..."
            uv sync --frozen --all-extras --no-extra=dev --no-install-project
            echo "Dependencies synced."
            ;;
    esac
fi
