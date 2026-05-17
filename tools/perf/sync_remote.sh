#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 --host <user@host> --source <path> --target <path>" >&2
}

remote_host=""
source_path=""
target_path=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            remote_host="${2:-}"
            shift 2
            ;;
        --source)
            source_path="${2:-}"
            shift 2
            ;;
        --target)
            target_path="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$remote_host" || -z "$source_path" || -z "$target_path" ]]; then
    usage
    exit 2
fi

source_path="${source_path%/}/"
target="${remote_host}:${target_path%/}/"

rsync_cmd=(
    rsync
    -az
    --delete
    --exclude AGENTS.md
    --exclude build/
    --exclude 'build*/'
    --exclude build-verify/
    --exclude '*/_deps/'
    --exclude '__pycache__/'
    --exclude '*.pyc'
    --exclude 'tools/perf/results/*'
    --exclude '.env'
    --exclude '.env.*'
    --exclude '*.pem'
    --exclude '*.key'
    --exclude '*.p12'
    --exclude '*.pfx'
    --exclude '*.cookie'
    -e "ssh -o StrictHostKeyChecking=no"
    "$source_path"
    "$target"
)

if [[ -n "${GRIDFLUX_SSH_PASSWORD:-}" ]]; then
    if ! command -v sshpass >/dev/null 2>&1; then
        echo "sshpass is required when GRIDFLUX_SSH_PASSWORD is set" >&2
        exit 1
    fi
    SSHPASS="$GRIDFLUX_SSH_PASSWORD" sshpass -e "${rsync_cmd[@]}"
else
    "${rsync_cmd[@]}"
fi

echo "synced ${source_path} to ${remote_host}:${target_path%/}/"
