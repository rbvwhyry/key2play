#!/usr/bin/env bash

set -e # this option quits the file if a process returns a non-zero exit code
set -o pipefail # sets the exit code of a pipeline to the rightmost non-zero exit code
set -u # treat unset variables as an error
set -x # print the commands being executed

uv self update
