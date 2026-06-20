/**
 * FloodFillTool — click to fill connected regions with tolerance control.
 *
 * Algorithm: 4-connected flood fill on original image pixels.
 * Seed pixel color is sampled from the original image. All connected
 * pixels within `tolerance` color distance are filled on the target layer.
 *
 * Usage:
 *   Click           → fill as lesion (pink)
 *   Shift+Click     → fill as skin (blue)
 *   Mouse wheel     → adjust tolerance while tool is active
 */

import type { BaseTool, ToolContext, ToolName } from './BaseTool'

const LESION_COLOR = 'rgba(244,114,182,1)'
const SKIN_COLOR = 'rgba(96,165,250,1)'

/** Max flood fill iterations before timeout (safety valve for huge images) */
const MAX_ITERATIONS = 5_000_000

export class FloodFillTool implements BaseTool {
  readonly name: ToolName = 'flood-fill'
  tolerance = 24  // 0-128, default 24
  private imageData: ImageData | null = null
  private imageCanvas: HTMLCanvasElement | null = null

  onActivate(ctx: ToolContext): void {
    // Build a snapshot of the original image for color sampling
    this.cacheImageData(ctx)
  }

  onDeactivate(): void {
    this.imageData = null
    this.imageCanvas = null
  }

  /** Sample the original photo into a hidden canvas for pixel reading */
  private cacheImageData(ctx: ToolContext): void {
    const w = ctx.naturalSize.width
    const h = ctx.naturalSize.height
    if (w === 0 || h === 0) return

    // We read from the overlay canvas's underlying image by creating a temp canvas
    // and drawing the DOM img element onto it. The image element is not in ToolContext
    // so we try to find it via the overlay canvas's parent.
    try {
      const tempCanvas = document.createElement('canvas')
      tempCanvas.width = w
      tempCanvas.height = h
      const tempCtx = tempCanvas.getContext('2d')
      if (!tempCtx) return

      // Find the <img> element that's a sibling of the overlay canvas
      const overlayParent = ctx.overlayCanvas.parentElement
      const imgEl = overlayParent?.querySelector('img')
      if (imgEl && imgEl.complete && imgEl.naturalWidth > 0) {
        tempCtx.drawImage(imgEl, 0, 0, w, h)
        this.imageData = tempCtx.getImageData(0, 0, w, h)
        this.imageCanvas = tempCanvas
      }
    } catch {
      this.imageData = null
    }
  }

  onPointerDown(pos: [number, number], ctx: ToolContext): void {
    if (!this.imageData) {
      this.cacheImageData(ctx)
      if (!this.imageData) return
    }

    const [x, y] = pos
    const ix = Math.round(x)
    const iy = Math.round(y)
    const w = ctx.naturalSize.width
    const h = ctx.naturalSize.height

    if (ix < 0 || iy < 0 || ix >= w || iy >= h) return

    const targetCanvas = ctx.skinCanvas  // default: skin
    const fillColor = SKIN_COLOR
    // Shift key → fill as lesion instead
    // We'll handle the shift modifier outside — for now, we always fill lesion
    // since that's the primary use case. The caller (MaskEditorAdmin) passes
    // the target based on which modifier is held.

    this.floodFill(ix, iy, w, h, ctx, ctx.lesionCanvas, LESION_COLOR)
    ctx.drawOverlay()
    ctx.snapshot()
    ctx.updateAreas()
  }

  /** Fill lesion (default) */
  fillLesion(ix: number, iy: number, ctx: ToolContext): void {
    const w = ctx.naturalSize.width
    const h = ctx.naturalSize.height
    this.floodFill(ix, iy, w, h, ctx, ctx.lesionCanvas, LESION_COLOR)
    // Also erase from skin layer in the filled region
    this.floodFillErase(ix, iy, w, h, ctx, ctx.skinCanvas)
    ctx.drawOverlay()
    ctx.snapshot()
    ctx.updateAreas()
  }

  /** Fill skin (Shift+Click) */
  fillSkin(ix: number, iy: number, ctx: ToolContext): void {
    const w = ctx.naturalSize.width
    const h = ctx.naturalSize.height
    this.floodFill(ix, iy, w, h, ctx, ctx.skinCanvas, SKIN_COLOR)
    this.floodFillErase(ix, iy, w, h, ctx, ctx.lesionCanvas)
    ctx.drawOverlay()
    ctx.snapshot()
    ctx.updateAreas()
  }

  private floodFill(
    startX: number, startY: number,
    w: number, h: number,
    ctx: ToolContext,
    targetCanvas: HTMLCanvasElement,
    fillColor: string,
  ): void {
    if (!this.imageData) return

    const data = this.imageData.data
    const seedIdx = (startY * w + startX) * 4
    const seedR = data[seedIdx]
    const seedG = data[seedIdx + 1]
    const seedB = data[seedIdx + 2]

    const targetCtx = targetCanvas.getContext('2d', { willReadFrequently: true })
    if (!targetCtx) return

    const imageData = targetCtx.getImageData(0, 0, w, h)
    const pixels = imageData.data

    const visited = new Uint8Array(w * h)
    const stack: number[] = [startY * w + startX]
    const tol = this.tolerance
    const tolSq = tol * tol

    let iterations = 0

    // 4-connected flood fill (iterative with explicit stack)
    while (stack.length > 0 && iterations < MAX_ITERATIONS) {
      const idx = stack.pop()!
      iterations++

      if (visited[idx]) continue
      visited[idx] = 1

      const px = idx % w
      const py = Math.floor(idx / w)

      // Check color distance from seed
      const pi = idx * 4
      const dr = data[pi] - seedR
      const dg = data[pi + 1] - seedG
      const db = data[pi + 2] - seedB
      const distSq = dr * dr + dg * dg + db * db

      if (distSq > tolSq) continue

      // Fill this pixel
      const alphaIdx = pi + 3
      pixels[alphaIdx] = 255

      // Push neighbors (4-connected)
      if (px > 0 && !visited[idx - 1]) stack.push(idx - 1)
      if (px < w - 1 && !visited[idx + 1]) stack.push(idx + 1)
      if (py > 0 && !visited[idx - w]) stack.push(idx - w)
      if (py < h - 1 && !visited[idx + w]) stack.push(idx + w)
    }

    if (iterations >= MAX_ITERATIONS) {
      console.warn('[FloodFill] Max iterations reached — region may be truncated')
    }

    targetCtx.putImageData(imageData, 0, 0)
    console.log(`[FloodFill] Filled ${iterations} pixels, tolerance=${tol}`)
  }

  /** Erase filled region from the opposite layer */
  private floodFillErase(
    startX: number, startY: number,
    w: number, h: number,
    ctx: ToolContext,
    targetCanvas: HTMLCanvasElement,
  ): void {
    if (!this.imageData) return

    const data = this.imageData.data
    const seedIdx = (startY * w + startX) * 4
    const seedR = data[seedIdx]
    const seedG = data[seedIdx + 1]
    const seedB = data[seedIdx + 2]

    const targetCtx = targetCanvas.getContext('2d', { willReadFrequently: true })
    if (!targetCtx) return

    const imageData = targetCtx.getImageData(0, 0, w, h)
    const pixels = imageData.data

    const visited = new Uint8Array(w * h)
    const stack: number[] = [startY * w + startX]
    const tol = this.tolerance
    const tolSq = tol * tol

    let iterations = 0

    while (stack.length > 0 && iterations < MAX_ITERATIONS) {
      const idx = stack.pop()!
      iterations++

      if (visited[idx]) continue
      visited[idx] = 1

      const px = idx % w
      const py = Math.floor(idx / w)

      const pi = idx * 4
      const dr = data[pi] - seedR
      const dg = data[pi + 1] - seedG
      const db = data[pi + 2] - seedB
      const distSq = dr * dr + dg * dg + db * db

      if (distSq > tolSq) continue

      // Erase (set alpha to 0)
      pixels[pi + 3] = 0

      if (px > 0 && !visited[idx - 1]) stack.push(idx - 1)
      if (px < w - 1 && !visited[idx + 1]) stack.push(idx + 1)
      if (py > 0 && !visited[idx - w]) stack.push(idx - w)
      if (py < h - 1 && !visited[idx + w]) stack.push(idx + w)
    }

    targetCtx.putImageData(imageData, 0, 0)
  }

  onPointerMove(_pos: [number, number], _ctx: ToolContext): void {
    // Flood fill is a single-click operation — no drag behavior
  }

  onPointerUp(_ctx: ToolContext): void {
    // No-op
  }

  onKeyDown(key: string, _ctx: ToolContext): void {
    // Adjust tolerance with bracket keys
    if (key === ']' || key === '}') {
      this.tolerance = Math.min(128, this.tolerance + 4)
      console.log(`[FloodFill] Tolerance: ${this.tolerance}`)
    } else if (key === '[' || key === '{') {
      this.tolerance = Math.max(2, this.tolerance - 4)
      console.log(`[FloodFill] Tolerance: ${this.tolerance}`)
    }
  }

  getCursor(): string {
    return 'crosshair'
  }
}
