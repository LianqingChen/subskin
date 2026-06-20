/**
 * BrushTool — paint skin or lesion regions with a circular brush.
 *
 * Extracted from MaskEditorAdmin.vue. Handles:
 * - Freehand painting with variable brush size
 * - Mutual exclusion (painting skin erases lesion in same spot, and vice versa)
 * - Sub-class: skin-brush (blue) and lesion-brush (pink)
 */

import type { BaseTool, ToolContext, ToolName } from './BaseTool'

const SKIN_COLOR = 'rgba(96,165,250,1)'
const LESION_COLOR = 'rgba(244,114,182,1)'

function getCtx(canvas: HTMLCanvasElement | null): CanvasRenderingContext2D | null {
  return canvas?.getContext('2d', { willReadFrequently: true }) || null
}

function paintAt(
  targetCanvas: HTMLCanvasElement,
  x: number, y: number,
  fromX: number, fromY: number,
  color: string,
  erase: boolean,
  brushSize: number,
) {
  const ctx = getCtx(targetCanvas)
  if (!ctx) return
  ctx.globalCompositeOperation = erase ? 'destination-out' : 'source-over'
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = brushSize * 2
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(fromX, fromY)
  ctx.lineTo(x, y)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(x, y, brushSize, 0, Math.PI * 2)
  ctx.fill()
  ctx.globalCompositeOperation = 'source-over'
}

export class BrushTool implements BaseTool {
  readonly name: ToolName
  private lastPos: [number, number] = [0, 0]
  private painting = false

  constructor(name: 'skin-brush' | 'lesion-brush') {
    this.name = name
  }

  get isSkin(): boolean {
    return this.name === 'skin-brush'
  }

  onActivate(_ctx: ToolContext): void {
    this.painting = false
  }

  onDeactivate(): void {
    this.painting = false
  }

  onPointerDown(pos: [number, number], ctx: ToolContext): void {
    this.painting = true
    this.lastPos = pos
    const [x, y] = pos

    const target = this.isSkin ? ctx.skinCanvas : ctx.lesionCanvas
    const color = this.isSkin ? SKIN_COLOR : LESION_COLOR

    // Paint on target layer
    paintAt(target, x, y, x, y, color, false, ctx.brushSize)

    // Erase from opposite layer to avoid double-counting
    if (this.isSkin) {
      paintAt(ctx.lesionCanvas, x, y, x, y, LESION_COLOR, true, ctx.brushSize)
    } else {
      paintAt(ctx.skinCanvas, x, y, x, y, SKIN_COLOR, true, ctx.brushSize)
    }

    ctx.drawOverlay()
  }

  onPointerMove(pos: [number, number], ctx: ToolContext): void {
    if (!this.painting) return
    const [x, y] = pos

    const target = this.isSkin ? ctx.skinCanvas : ctx.lesionCanvas
    const color = this.isSkin ? SKIN_COLOR : LESION_COLOR

    paintAt(target, x, y, this.lastPos[0], this.lastPos[1], color, false, ctx.brushSize)

    if (this.isSkin) {
      paintAt(ctx.lesionCanvas, x, y, this.lastPos[0], this.lastPos[1], LESION_COLOR, true, ctx.brushSize)
    } else {
      paintAt(ctx.skinCanvas, x, y, this.lastPos[0], this.lastPos[1], SKIN_COLOR, true, ctx.brushSize)
    }

    this.lastPos = [x, y]
    ctx.drawOverlay()
  }

  onPointerUp(ctx: ToolContext): void {
    if (this.painting) {
      this.painting = false
      ctx.snapshot()
      ctx.updateAreas()
    }
  }

  onKeyDown(_key: string, _ctx: ToolContext): void {
    // No tool-specific key bindings
  }

  getCursor(): string {
    return 'crosshair'
  }
}
