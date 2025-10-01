#!/bin/bash
# guesses the disk to image and copies it with gzip compression
# gzipped image is output to the current directory

set -e # this option quits the file if a process returns a non-zero exit code
set -o pipefail # sets the exit code of a pipeline to the rightmost non-zero exit code
set -u # treat unset variables as an error
set -x # print the commands being executed

TIMESTAMP="$(date +%Y-%m-%d_%H_%M_%S)"
TMPDIR=${TMPDIR-/tmp}
TEMPFILE="$(mktemp "sdcard_image_$(date +%Y-%m-%d_%H_%M_%S).img.gz.XXXXXXXXX")"
DESTFILE="sdcard_image_${TIMESTAMP}.img.gz"

# copied from https://raspberrypi.stackexchange.com/a/72047

# Find disk with Linux partition (works for Raspbian)
# Modified for PINN/NOOBS
DSK=$(diskutil list | grep "Linux" | sed 's/.*\(disk[0-9]\).*/\1/' | uniq)
if [ ! $DSK ]; then
    echo "Disk not found"
    exit
fi

diskutil unmountDisk /dev/$DSK

echo "please wait - This takes some time"
echo "Ctl+T to show progress!"

time sudo dd if=/dev/r$DSK bs=4m status=progress | gzip -9 > "$TMPDIR/$TEMPFILE"

echo "imaging completed - now renaming tempfile to destination"

mv -n "$TMPDIR/$TEMPFILE" "$DESTFILE"
