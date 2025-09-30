#!/usr/bin/env bash

set -e # this option quits the file if a process returns a non-zero exit code
set -o pipefail # sets the exit code of a pipeline to the rightmost non-zero exit code
set -u # treat unset variables as an error
set -x # print the commands being executed

shopt -s nullglob

# create gh-pages directory if it doesn't already exist
if [ -d gh-pages ]; then
    git worktree add ./gh-pages gh-pages
fi

FILELIST=(./*.py ./*.sh ./**/*.py ./crazy-sky-250204/*.* ./crazy-sky-250204/src/*.* ./crazy-sky-250204/src/static/**/*.*)

echo "${FILELIST[@]}"

HASH="$(sha256sum "${FILELIST[@]}" | sha256sum)"
HASH_PREFIX="${HASH:0:10}"
DATE="$(date -u '+%Y_%m_%d_%H_%M_%S')"
ZIPFILE_NAME="release_${DATE}_${HASH_PREFIX}.zip"
zip "${ZIPFILE_NAME}" "${FILELIST[@]}"
cp "${ZIPFILE_NAME}" gh-pages/
jq ".[.| length] |= . + \"${ZIPFILE_NAME}\"" gh-pages/releases.json | sponge gh-pages/releases.json
