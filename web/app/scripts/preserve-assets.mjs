#!/usr/bin/env node
// Keeps hashed chunks from previous builds reachable after a deploy, so PWA
// clients still running an old index.html don't 404 on lazy imports.
//
//   node scripts/preserve-assets.mjs save <outDir>     (before vite build)
//   node scripts/preserve-assets.mjs restore <outDir>  (after vite build)
//
// The pool lives outside the nginx web root. Vite still empties outDir, so the
// service-worker precache manifest only lists the new build's files.
import fs from 'node:fs'
import path from 'node:path'

const RETENTION_MS = 14 * 24 * 60 * 60 * 1000
const POOL_ROOT = '/var/tmp/subskin-prev-assets'

const [, , command, outDirArg] = process.argv
if (!['save', 'restore'].includes(command) || !outDirArg) {
  console.error('usage: preserve-assets.mjs <save|restore> <outDir>')
  process.exit(2)
}

const outDir = path.resolve(outDirArg)
const assetsDir = path.join(outDir, 'assets')
const poolDir = path.join(POOL_ROOT, path.basename(outDir))

function listFiles(dir) {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes: true }).filter((d) => d.isFile()).map((d) => d.name)
}

function copyKeepingMtime(src, dst) {
  fs.copyFileSync(src, dst)
  const { atime, mtime } = fs.statSync(src)
  fs.utimesSync(dst, atime, mtime)
}

function referencedNames() {
  const refs = new Set()
  for (const entry of ['index.html', 'sw.js']) {
    const file = path.join(outDir, entry)
    if (!fs.existsSync(file)) continue
    for (const m of fs.readFileSync(file, 'utf8').matchAll(/assets\/([^"'`)\s?#]+)/g)) refs.add(m[1])
  }
  return refs
}

function isExpired(file) {
  return Date.now() - fs.statSync(file).mtimeMs > RETENTION_MS
}

if (command === 'save') {
  fs.mkdirSync(poolDir, { recursive: true })
  let n = 0
  // Fresh mtime on save: retention counts from the last time a file was live, not from its build.
  for (const name of listFiles(assetsDir)) {
    fs.copyFileSync(path.join(assetsDir, name), path.join(poolDir, name))
    n++
  }
  console.log(`[preserve-assets] saved ${n} files from ${assetsDir} into ${poolDir}`)
  process.exit(0)
}

if (!fs.existsSync(path.join(outDir, 'index.html'))) {
  console.error(`[preserve-assets] ${outDir}/index.html missing; refusing to restore into a failed build`)
  process.exit(1)
}

const current = new Set(listFiles(assetsDir))
const refs = referencedNames()
let restored = 0
let pruned = 0

for (const name of listFiles(poolDir)) {
  const pooled = path.join(poolDir, name)
  if (isExpired(pooled) && !refs.has(name)) {
    fs.rmSync(pooled)
    pruned++
    continue
  }
  if (!current.has(name)) {
    copyKeepingMtime(pooled, path.join(assetsDir, name))
    restored++
  }
}

console.log(`[preserve-assets] restored ${restored} previous-build files, pruned ${pruned} expired files`)
