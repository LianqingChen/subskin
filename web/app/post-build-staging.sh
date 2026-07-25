#!/bin/bash
# Copy VitePress encyclopedia content to staging build directory
cp -r /root/subskin/web/vitepress/docs/.vitepress/dist /usr/share/nginx/html/subskin-staging/wiki-content 2>/dev/null || true

# Fix permissions so nginx (running as `nginx` user) can read the build output.
# Build processes sometimes run with a restrictive umask (e.g. 0077 in some
# agent/sandbox shells), which produces 0600 files and 0700 dirs → 403 Forbidden.
chmod -R a+rX /usr/share/nginx/html/subskin-staging
echo "[staging] post-build done"
