#!/bin/bash

set -exo pipefail

shopt -s nullglob

FILELIST=(./*.py ./**/*.py ./crazy-sky-250204/*.* ./crazy-sky-250204/src/*.* ./crazy-sky-250204/src/static/**/*.*)

echo "${FILELIST[@]}"

HASH="$(sha256sum "${FILELIST[@]}" | sha256sum)"
HASH_PREFIX="${HASH:0:10}"
DATE="$(date -I)"
ZIPFILE_NAME="release_${DATE}_${HASH_PREFIX}.zip"
zip "${ZIPFILE_NAME}" ${FILELIST[@]}
