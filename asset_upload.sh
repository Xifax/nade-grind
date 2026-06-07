#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
    set -a  # automatically export all variables
    source .env
    set +a
else
    echo "Warning: .env file not found. PRIVATE_TOKEN must be set manually."
fi

# TODO: convert to bb
# TODO: check PROJECT names and url paths like anki_export (also parametrize)

: "${PRIVATE_TOKEN:?Error: PRIVATE_TOKEN environment variable is not set}"

VERSION="0.5.0"
PROJECT="xifax/nade_grind"
PROJECT_ENCODED="xifax%2Fnade_grind"
RELEASE_NAME="v${VERSION}-nigiri"
NOTES="Linux BIN & Windows EXE"

command -v jq >/dev/null 2>&1 || { echo "Error: jq is required"; exit 1; }

declare -A FILES=(
    ["nade.bin"]="nade.bin"
    ["nade.exe"]="nade.exe"
)

# Check files exist
for f in "${FILES[@]}"; do
    [[ -f "$f" ]] || { echo "Error: File not found: $f"; exit 1; }
done

echo "=== Uploading packages to GitLab Package Registry ==="
for NAME in "${!FILES[@]}"; do
    LOCAL_FILE="${FILES[$NAME]}"
    PACKAGE_URL="https://gitlab.com/api/v4/projects/${PROJECT_ENCODED}/packages/generic/anki_export/${VERSION}/${NAME}"

    echo "Uploading ${LOCAL_FILE} ..."
    curl --fail --silent --show-error \
         --header "PRIVATE-TOKEN: ${PRIVATE_TOKEN}" \
         --upload-file "${LOCAL_FILE}" \
         "${PACKAGE_URL}"
done

echo "=== Creating/updating release ==="
glab release create "v${VERSION}" \
    --name "${RELEASE_NAME}" \
    --notes "${NOTES}" || true

echo "=== Syncing release asset links ==="
for NAME in "${!FILES[@]}"; do
    PACKAGE_URL="https://gitlab.com/api/v4/projects/${PROJECT_ENCODED}/packages/generic/anki_export/${VERSION}/${NAME}"

    LINK_ID=$(glab api "projects/${PROJECT_ENCODED}/releases/v${VERSION}/assets/links" \
        | jq -r ".[] | select(.name == \"${NAME}\") | .id")

    if [ -n "${LINK_ID}" ] && [ "${LINK_ID}" != "null" ]; then
        echo "Removing old link for ${NAME} (ID: ${LINK_ID})"
        glab api -X DELETE "projects/${PROJECT_ENCODED}/releases/v${VERSION}/assets/links/${LINK_ID}"
    fi

    echo "Creating asset link for ${NAME}"
    glab api -X POST "projects/${PROJECT_ENCODED}/releases/v${VERSION}/assets/links" \
        --field "name=${NAME}" \
        --field "url=${PACKAGE_URL}"
done

echo "✅ Done. Release v${VERSION} is ready."
