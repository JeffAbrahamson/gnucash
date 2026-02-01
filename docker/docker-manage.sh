#!/bin/bash

set -euo pipefail

export SSH_USER=$LOGNAME

cd "$(dirname "$0")"

action="${1:-}"
shift || true
case "$action" in
    sh)
        # Interactive shell - shares container across multiple shells
        docker compose up -d --build dev-sh
        docker compose exec dev-sh /usr/local/bin/entrypoint.sh /bin/bash

        # When shell exits, check if other shells are still running
        echo "Checking if other shells are running..."
        num_shells=$(docker compose exec dev-sh ps -eo tty,comm | awk '$1 ~ /^pts\// && $2=="bash" {print $1}' | sort -u | wc -l)
        if [ "$num_shells" -ne 0 ]; then
            echo "${num_shells} still running."
        else
            echo "No more shells detected, stopping container..."
            docker compose stop dev-sh
        fi
        ;;
    claude)
        # Claude Code - runs in ephemeral container
        # The entrypoint handles the special invocation needed for claude
        docker compose run --rm --build dev-claude claude
        ;;
    codex)
        # OpenAI Codex - runs in ephemeral container
        docker compose run --rm --build dev-codex codex
        ;;

    *)
        echo "Usage: ./docker-manage.sh sh|claude|codex"
        if [ -n "$action" ]; then
            echo "** Unrecognised action: \"$action\"."
        fi
        ;;
esac
