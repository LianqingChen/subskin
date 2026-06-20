/**
 * PolygonTool — click to place vertices, double-click or Enter to close.
 *
 * Usage:
 *   Click          → place vertex
 *   Double-click   → close polygon → fill as lesion
 *   Enter          → close polygon → fill as lesion
 *   Escape         → cancel / clear vertices
 *   Backspace      → remove last vertex
 *   Shift+Enter    → close → fill as skin
 */

import type { BaseTool, ToolContext, ToolName } from './BaseTool'

const LESION_COLOR = 'rgba(244,114,182,1)'
const SKIN_COLOR = 'rgba(96,165,250,1)'
const VERTEX_COLOR = '#fbbf24'
const EDGE_COLOR = '#fbbf24'
const VERTEX_RADIUS = 4

export class PolygonTool implements BaseTool {
  readonly name: ToolName = 'polygon'
  private vertices: [number, number][] = []
  private lastClickTime = 0

  onActivate(_ctx: ToolContext): void {
    this.vertices = []
  }

  onDeactivate(): void {
    this.vertices = []
  }

  onPointerDown(pos: [number, number], ctx: ToolContext): void {
    const now = Date.now()
    // Detect double-click (< 300ms between clicks)
    if (now - this.lastClickTime < 300 && this.vertices.length >= 3) {
      this.lastClickTime = 0
      this.closeAndFill(ctx, false)
      return
    }
    this.lastClickTime = now

    // Add vertex
    this.vertices.push(pos)
    this.drawPolygon(ctx)
  }

  onPointerMove(_pos: [number, number], ctx: ToolContext): void {
    // Could draw a preview line from last vertex to cursor,
    // but for simplicity we just redraw current state
    if (this.vertices.length > 0) {
      this.drawPolygon(ctx)
    }
  }

  onPointerUp(_ctx: ToolContext): void {
    // No-op: vertices are added on pointer down
  }

  onKeyDown(key: string, ctx: ToolContext): void {
    if (key === 'Enter') {
      if (this.vertices.length >= 3) {
        this.closeAndFill(ctx, false)
      }
    } else if (key === 'Escape') {
      this.vertices = []
      ctx.drawOverlay()
    } else if (key === 'Backspace') {
      this.vertices.pop()
      if (this.vertices.length > 0) {
        this.drawPolygon(ctx)
      } else {
        ctx.drawOverlay()
      }
    }
  }

  private closeAndFill(ctx: ToolContext, _asSkin: boolean): void {
    if (this.vertices.length < 3) return

    // Build closed polygon path
    const first = this.vertices[0]
    const polygon: [number, number][] = [...this.vertices, [first[0], first[1]]]

    this.drawPolygon(ctx)

    // Fill lesion layer
    this.fillPolygon(polygon, ctx.lesionCanvas, LESION_COLOR, ctx)
    // Erase from skin layer
    this.fillPolygon(polygon, ctx.skinCanvas, 'rgba(0,0,0,0)', ctx)

    this.vertices = []
    ctx.drawOverlay()
    ctx.snapshot()
    ctx.updateAreas()
  }

  private drawPolygon(ctx: ToolContext): void {
    ctx.drawOverlay()

    const overlayCtx = ctx.overlayCanvas.getContext('2d')
    if (!overlayCtx || this.vertices.length === 0) return

    // Draw edges
    overlayCtx.strokeStyle = EDGE_COLOR
    overlayCtx.lineWidth = 2
    overlayCtx.setLineDash([6, 4])
    overlayCtx.beginPath()
    overlayCtx.moveTo(this.vertices[0][0], this.vertices[0][1])
    for (let i = 1; i < this.vertices.length; i++) {
      overlayCtx.lineTo(this.vertices[i][0], this.vertices[i][1])
    }
    overlayCtx.stroke()
    overlayCtx.setLineDash([])

    // Draw vertices
    for (const [vx, vy] of this.vertices) {
      overlayCtx.fillStyle = VERTEX_COLOR
      overlayCtx.beginPath()
      overlayCtx.arc(vx, vy, VERTEX_RADIUS, 0, Math.PI * 2)
      overlayCtx.fill()
      overlayCtx.strokeStyle = '#0f172a'
      overlayCtx.lineWidth = 1.5
      overlayCtx.stroke()
    }
  }

  /** Scanline polygon fill (same algorithm as LassoTool) */
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

    const edges: { yMin: number; yMax: number; x: number; slope: number }[] = []
    for (let i = 0; i < polygon.length - 1; i++) {
      const [x1, y1] = polygon[i]
      const [x2, y2] = polygon[i + 1]
      const yMin = Math.min(y1, y2)
      const yMax = Math.max(y1, y2)
      if (yMax === yMin) continue
      edges.push({
        yMin,
        yMax,
        x: y1 < y2 ? x1 : x2,
        slope: (x2 - x1) / (y2 - y1),
      })
    }

    edges.sort((a, b) => a.yMin - b.yMin)

    const imageData = targetCtx.getImageData(0, 0, w, h)
    const pixels = imageData.data
    const isErase = color === 'rgba(0,0,0,0)'

    const minY = Math.max(0, Math.floor(Math.min(...polygon.map(p => p[1]))))
    const maxY = Math.min(h - 1, Math.ceil(Math.max(...polygon.map(p => p[1]))))

    for (let y = minY; y <= maxY; y++) {
      const activeX: number[] = []
      for (const edge of edges) {
        if (y >= edge.yMin && y < edge.yMax) {
          activeX.push(edge.x + (y - edge.yMin) * edge.slope)
        }
      }
      activeX.sort((a, b) => a - b)

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

  getCursor(): string {
    return 'crosshair'
  }
}
