#!/bin/sh
# Uploads our pieces (the files catalog/grade.json › ours names, from media/ours/) as assets of the GitHub release named in catalog/grade.json's ours_base.
# Run once after the repo exists, and again (with --clobber) when a piece changes. Needs gh, logged in.
#   tools/release_ours.sh            create the release and upload everything
#   tools/release_ours.sh --clobber  replace the files in an existing release
set -e
cd "$(dirname "$0")/.."
TAG=$(python3 -c 'import json;print(json.load(open("catalog/grade.json"))["ours_base"].rstrip("/").split("/")[-1])')
FILES=$(python3 -c 'import json;print(" ".join("media/ours/"+o["file"] for o in json.load(open("catalog/grade.json"))["ours"]))')
REPO=$(python3 -c 'import json;b=json.load(open("catalog/grade.json"))["ours_base"].split("/");print(b[3]+"/"+b[4])')
if [ "$1" = "--clobber" ]; then
  gh release upload "$TAG" $FILES --repo "$REPO" --clobber
else
  gh release create "$TAG" $FILES --repo "$REPO" --title "KÖLJA TV: our pieces ($TAG)" \
    --notes "Vignettes, idents, station card and break bumpers aired by KÖLJA TV. Made by KÖLJA. All rights reserved."
fi
