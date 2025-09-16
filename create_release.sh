#!/bin/bash

set -exo pipefail

shopt -s nullglob

FILELIST=(./*.py ./*.sh ./**/*.py ./crazy-sky-250204/*.* ./crazy-sky-250204/src/*.* ./crazy-sky-250204/src/static/**/*.*)

echo "${FILELIST[@]}"

HASH="$(sha256sum "${FILELIST[@]}" | sha256sum)"
HASH_PREFIX="${HASH:0:10}"
DATE="$(date -u '+%Y_%m_%d_%H_%M_%S')"
ZIPFILE_NAME="release_${DATE}_${HASH_PREFIX}.zip"
zip "${ZIPFILE_NAME}" "${FILELIST[@]}"
cp "${ZIPFILE_NAME}" gh-pages/
jq ".[.| length] |= . + \"${ZIPFILE_NAME}\"" gh-pages/releases.json | sponge gh-pages/releases.json
