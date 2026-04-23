#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="tutor-assistant-local"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "${PROJECT_ROOT}/.logs" "${PROJECT_ROOT}/secrets" "${PROJECT_ROOT}/memory"

# Build quietly so chat UX matches local CLI experience.
docker build -q -t "${IMAGE_NAME}" "${PROJECT_ROOT}" >/dev/null

if [[ $# -eq 0 ]]; then
  set -- chat
elif [[ "${1}" == -* ]]; then
  set -- chat "$@"
fi

if [[ -t 0 && -t 1 ]]; then
  exec docker run --rm -it \
    --env-file "${PROJECT_ROOT}/secrets/.env" \
    -e GOOGLE_CREDENTIALS_PATH=/data/secrets/credentials.json \
    -e GOOGLE_TOKEN_PATH=/data/secrets/token.json \
    -e TUTOR_AGENT_MEMORY_PATH=/data/memory/.agent_memory.json \
    -e TUTOR_LOG_DIR=/data/.logs \
    -v "${PROJECT_ROOT}:/data" \
    "${IMAGE_NAME}" \
    "$@"
fi

exec docker run --rm \
  --env-file "${PROJECT_ROOT}/secrets/.env" \
  -e GOOGLE_CREDENTIALS_PATH=/data/secrets/credentials.json \
  -e GOOGLE_TOKEN_PATH=/data/secrets/token.json \
  -e TUTOR_AGENT_MEMORY_PATH=/data/memory/.agent_memory.json \
  -e TUTOR_LOG_DIR=/data/.logs \
  -v "${PROJECT_ROOT}:/data" \
  "${IMAGE_NAME}" \
  "$@"
