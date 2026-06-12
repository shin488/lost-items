#!/usr/bin/env bash
set -euo pipefail

BUILD_DIR="build/web"

if [ ! -d "$BUILD_DIR" ]; then
  echo "Error: $BUILD_DIR not found. Run 'flet build web' first."
  exit 1
fi

# 1. Manifest
cp pwa/manifest.json "$BUILD_DIR/manifest.json"

# 2. Service worker
cp pwa/service-worker.js "$BUILD_DIR/flutter_service_worker.js"

# 3. iOS/Android meta tags in <head>
# Use the existing apple-touch-icon-192.png (iOS scales as needed)
sed -i '/<\/title>/a\
  <meta name="theme-color" content="#00695C">\
  <meta name="description" content="なくした物の記録·分析アプリ">\
  <meta name="apple-mobile-web-app-capable" content="yes">\
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\
  <meta name="apple-mobile-web-app-title" content="なくしもの探知機">\
  <link rel="apple-touch-icon" sizes="180x180" href="icons/apple-touch-icon-192.png">\
  <link rel="apple-touch-icon" sizes="152x152" href="icons/apple-touch-icon-192.png">\
  <link rel="apple-touch-icon" sizes="120x120" href="icons/apple-touch-icon-192.png">\
  <link rel="apple-touch-icon" sizes="76x76" href="icons/apple-touch-icon-192.png">' "$BUILD_DIR/index.html"

echo "PWA patched successfully"
