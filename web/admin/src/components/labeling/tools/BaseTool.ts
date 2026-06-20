/**
 * BaseTool — pluggable canvas tool interface for MaskEditorAdmin.
 *
 * Each tool encapsulates its own pointer/keyboard handling.
 * MaskEditorAdmin acts as a host: it owns the canvases and delegates
 * events to the active tool.
 */

export interface ToolContext {
  /** Off-screen canvas for skin region paint (blue) */
  skinCanvas: HTMLCanvasElement
  /** Off-screen canvas for lesion region paint (pink) */
  lesionCanvas: HTMLCanvasElement
  /** On-screen overlay canvas (composited skin + lesion) */
  overlayCanvas: HTMLCanvasElement
  /** Natural image dimensions in pixels */
  naturalSize: { width: number; height: number }
  /** Current brush/tool size in natural pixels */
  brushSize: number
  /** Current pan/zoom transform */
  transform: { scale: number; offsetX: number; offsetY: number }
  /** Convert client coordinates to natural image coordinates */
  clientToImage: (clientX: number, clientY: number) => [number, number] | null
  /** Draw the overlay (composite skin + lesion onto overlay canvas) */
  drawOverlay: () => void
  /** Snapshot current canvas state to undo history */
  snapshot: () => void
  /** Update area percentages from canvas pixel counts */
  updateAreas: () => void
}

export type ToolName = 'skin-brush' | 'lesion-brush' | 'eraser' | 'flood-fill' | 'lasso' | 'polygon' | 'grabcut'

export interface ToolDef {
  name: ToolName
  label: string
  icon: string          // remixicon class
  shortcut: string      // single uppercase key
  cursor: string        // CSS cursor value
  /** Whether this tool is available (e.g., GrabCut only in M3) */
  available: boolean
}

export const ALL_TOOLS: ToolDef[] = [
  { name: 'skin-brush',   label: '皮肤画笔', icon: 'ri-brush-line',          shortcut: 'B', cursor: 'crosshair', available: true },
  { name: 'lesion-brush', label: '白斑画笔', icon: 'ri-brush-2-line',        shortcut: 'L', cursor: 'crosshair', available: true },
  { name: 'flood-fill',   label: '智能填充', icon: 'ri-contrast-drop-2-line',shortcut: 'G', cursor: 'crosshair', available: true },
  { name: 'lasso',        label: '套索选择', icon: 'ri-shapes-line',         shortcut: 'S', cursor: 'crosshair', available: true },
  { name: 'polygon',      label: '多边形选择',icon: 'ri-pentagon-line',       shortcut: 'P', cursor: 'crosshair', available: true },
  { name: 'eraser',       label: '橡皮擦',   icon: 'ri-eraser-line',         shortcut: 'E', cursor: 'crosshair', available: true },
  { name: 'grabcut',      label: '智能分割', icon: 'ri-magic-line',          shortcut: 'C', cursor: 'crosshair', available: false },
]

export interface BaseTool {
  /** Unique tool identifier */
  readonly name: ToolName
  /** Called when tool becomes active */
  onActivate(ctx: ToolContext): void
  /** Called when tool is deactivated (switch to another tool) */
  onDeactivate(): void
  /** Pointer down on the overlay canvas (natural image coords) */
  onPointerDown(pos: [number, number], ctx: ToolContext): void
  /** Pointer move (natural image coords) */
  onPointerMove(pos: [number, number], ctx: ToolContext): void
  /** Pointer up */
  onPointerUp(ctx: ToolContext): void
  /** Keydown while tool is active (single key string) */
  onKeyDown(key: string, ctx: ToolContext): void
  /** Get current cursor based on tool state */
  getCursor(): string
}
