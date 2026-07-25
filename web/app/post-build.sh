cp -r /root/subskin/web/vitepress/docs/.vitepress/dist /usr/share/nginx/html/subskin/wiki-content 2>/dev/null || true

# Fix permissions so nginx (running as `nginx` user) can read the build output.
# See post-build-staging.sh for rationale.
chmod -R a+rX /usr/share/nginx/html/subskin
