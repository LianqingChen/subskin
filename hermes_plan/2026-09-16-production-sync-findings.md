# Findings

- Main production npm run deploy:prod includes vue-tsc -b then production Vite config; staging default output separate.
- Admin npm run build targets production directly; staging preview must override base and outDir.
- rag.py still says manual UI staging-only; remove as part of this full publication.
