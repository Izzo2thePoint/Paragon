#!/bin/sh
# Rebuilds vendor/anthropic-sdk.min.js: the official Anthropic JS SDK as one
# browser file that sets window.Anthropic. scan.py embeds it in the page.
set -e
VERSION=${1:-0.128.0}
DIR=$(mktemp -d)
cd "$DIR"
npm init -y >/dev/null
npm install "@anthropic-ai/sdk@$VERSION" esbuild >/dev/null
echo 'import Anthropic from "@anthropic-ai/sdk"; window.Anthropic = Anthropic;' > entry.js
npx esbuild entry.js --bundle --minify --format=iife --platform=browser --target=es2020 --outfile=out.js
cd - >/dev/null
cp "$DIR/out.js" "$(dirname "$0")/anthropic-sdk.min.js"
echo "Built @anthropic-ai/sdk@$VERSION"
