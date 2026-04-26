#!/usr/bin/env bash

set -e # this option quits the file if a process returns a non-zero exit code
set -o pipefail # sets the exit code of a pipeline to the rightmost non-zero exit code
set -u # treat unset variables as an error
set -x # print the commands being executed

shopt -s nullglob


pushd crazy-sky-250204
npm install
npm run build
popd


FILELIST=(./*.py ./pyproject.toml ./requirements.txt ./webinterface/*.py ./lib/*.py ./config/* ./webinterface/crazy_sky_dist/index.html ./webinterface/crazy_sky_dist/assets/*)

echo "${FILELIST[@]}"
HASH="$(sha256sum "${FILELIST[@]}" | sha256sum)"
HASH_PREFIX="${HASH:0:10}"
DATE="$(date -u '+%Y_%m_%d_%H_%M_%S')"
RELEASE_NAME="release_${DATE}_${HASH_PREFIX}"
ZIPFILE_NAME="${RELEASE_NAME}.zip"
zip "${ZIPFILE_NAME}" "${FILELIST[@]}"

# echo "check to make sure it looks right"
# DIRNAME="release_${DATE}_${HASH_PREFIX}"
# unzip -d "${DIRNAME}" "${ZIPFILE_NAME}"
# pushd "${DIRNAME}"
# sudo uv run visualizer.py -a app

# create gh-pages directory if it doesn't already exist
if [ ! -d gh-pages ]; then
    git worktree add ./gh-pages gh-pages
fi

cp "${ZIPFILE_NAME}" gh-pages/
jq ".[.| length] |= . + \"${ZIPFILE_NAME}\"" gh-pages/releases.json | sponge gh-pages/releases.json


echo "cd to gh-pages and commit new release"
pushd gh-pages
git reset
git add "${ZIPFILE_NAME}"
git add releases.json
git commit -m "add new release ${RELEASE_NAME}"

echo "push to github"
read -p "Press Enter to continue" </dev/tty
