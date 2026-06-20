#!/bin/bash
# Copy VitePress encyclopedia content to staging build directory
cp -r /root/subskin/web/vitepress/docs/.vitepress/dist /usr/share/nginx/html/subskin-staging/wiki-content 2>/dev/null || true
echo "[staging] post-build done"
