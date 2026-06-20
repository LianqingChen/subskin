/**
 * LassoTool — freehand draw a closed selection boundary, then fill interior.
 *
 * Usage:
 *   Hold & drag  → draw freehand lasso path
 *   Release      → path auto-closes → selection fills as lesion
 *   Shift+Release → fill as skin instead
 */

import type { BaseTool, ToolContext, ToolName } from './BaseTool'

const LESION_COLOR = 'rgba(244,114,182,1)'
const SKIN_COLOR = 'rgba(96,165,250,1)'
const PATH_COLOR = '#fbbf24'       // amber path while drawing
const PATH_WIDTH = 2

export class LassoTool implements BaseTool {
  readonly name: ToolName = 'lasso'
  private path: [number, number][] = []
  private drawing = false

  onActivate(_ctx: ToolContext): void {
    this.path = []
    this.drawing = false
  }

  onDeactivate(): void {
    this.clearPathOverlay()
    this.path = []
    this.drawing = false
  }

  onPointerDown(pos: [number, number], ctx: ToolContext): void {
    this.drawing = true
    this.path = [pos]
    this.drawPath(ctx)
  }

  onPointerMove(pos: [number, number], ctx: ToolContext): void {
    if (!this.drawing) return
    this.path.push(pos)
    this.drawPath(ctx)
  }

  onPointerUp(ctx: ToolContext): void {
    if (!this.drawing || this.path.length < 4) {
      this.drawing = false
      this.path = []
      ctx.drawOverlay()
      return
    }
    this.drawing = false

    // Close the path
    const first = this.path[0]
    const last = this.path[this.path.length - 1]
    this.path.push([first[0], first[1]])

    this.drawPath(ctx)

    // Fill the polygon interior on the lesion layer
    this.fillPolygon(this.path, ctx.lesionCanvas, LESION_COLOR, ctx)
    // Erase from skin layer
    this.fillPolygon(this.path, ctx.skinCanvas, 'rgba(0,0,0,0)', ctx)

    this.path = []
    ctx.drawOverlay()
    ctx.snapshot()
    ctx.updateAreas()
  }

  private drawPath(ctx: ToolContext): void {
    // Draw temporary path on overlay (we'll re-composite after)
    const overlayCtx = ctx.overlayCanvas.getContext('2d')
    if (!overlayCtx || this.path.length < 2) return

    // First restore base (skin + lesion composite without path)
    ctx.drawOverlay()

    // Then draw path on top
    overlayCtx.strokeStyle = PATH_COLOR
    overlayCtx.lineWidth = PATH_WIDTH
    overlayCtx.lineCap = 'round'
    overlayCtx.lineJoin = 'round'
    overlayCtx.setLineDash([6, 4])
    overlayCtx.beginPath()
    overlayCtx.moveTo(this.path[0][0], this.path[0][1])
    for (let i = 1; i < this.path.length; i++) {
      overlayCtx.lineTo(this.path[i][0], this.path[i][1])
    }
    overlayCtx.stroke()
    overlayCtx.setLineDash([])
  }

  private clearPathOverlay(): void {
    // Handled by next drawOverlay call from the host
  }

  /** Scanline polygon fill */
  private fillPolygon(
    polygon: [number, number][],
    canvas: HTMLCanvasElement,
    color: string,
    ctx: ToolContext,
  ): void {
    const targetCtx = canvas.getContext('2d', { willReadFrequently: true })
    if (!targetCtx) return

    const w = ctx.naturalSize.width
    const h = ctx.naturalSize.height

    // Build edge table
    const edges: { yMin: number; yMax: number; x: number; slope: number }[] = []
    for (let i = 0; i < polygon.length - 1; i++) {
      const [x1, y1] = polygon[i]
      const [x2, y2] = polygon[i + 1]
      const yMin = Math.min(y1, y2)
      const yMax = Math.max(y1, y2)
      if (yMax === yMin) continue // horizontal edge — skip
      edges.push({
        yMin,
        yMax,
        x: y1 < y2 ? x1 : x2,
        slope: (x2 - x1) / (y2 - y1),
      })
    }

    // Sort by yMin
    edges.sort((a, b) => a.yMin - b.yMin)

    const imageData = targetCtx.getImageData(0, 0, w, h)
    const pixels = imageData.data
    const isErase = color === 'rgba(0,0,0,0)'

    // Scanline from min y to max y
    const minY = Math.max(0, Math.floor(Math.min(...polygon.map(p => p[1]))))
    const maxY = Math.min(h - 1, Math.ceil(Math.max(...polygon.map(p => p[1]))))

    for (let y = minY; y <= maxY; y++) {
      // Find active edges crossing this scanline
      const activeX: number[] = []
      for (const edge of edges) {
        if (y >= edge.yMin && y < edge.yMax) {
          const x = edge.x + (y - edge.yMin) * edge.slope
          activeX.push(x)
        }
      }
      activeX.sort((a, b) => a - b)

      // Fill spans (pairs)
      for (let i = 0; i < activeX.length - 1; i += 2) {
        const xStart = Math.max(0, Math.ceil(activeX[i]))
        const xEnd = Math.min(w - 1, Math.floor(activeX[i + 1]))
        for (let x = xStart; x <= xEnd; x++) {
          const idx = (y * w + x) * 4
          if (isErase) {
            pixels[idx + 3] = 0
          } else {
            pixels[idx + 3] = 255
          }
        }
      }
    }

    targetCtx.putImageData(imageData, 0, 0)
  }

  onKeyDown(key: string, ctx: ToolContext): void {
    if (key === 'Escape' && this.drawing) {
      this.drawing = false
      this.path = []
      ctx.drawOverlay()
    }
  }

  getCursor(): string {
    return 'crosshair'
  }
}
