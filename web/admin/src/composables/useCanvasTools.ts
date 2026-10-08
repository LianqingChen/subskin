/**
 * useCanvasTools — manages the active tool, tool switching, and tool lifecycle.
 *
 * Owns the tool instances and provides keyboard-shortcut-based switching.
 * Supports an optional whitelist: when provided, only whitelisted tools are
 * exposed/switchable (e.g. the workspace restricts to lesion-brush + eraser).
 */

import { ref, computed, shallowRef } from 'vue'
import type { BaseTool, ToolContext, ToolName } from '@/components/labeling/tools/BaseTool'
import { ALL_TOOLS } from '@/components/labeling/tools/BaseTool'
import { BrushTool } from '@/components/labeling/tools/BrushTool'
import { EraserTool } from '@/components/labeling/tools/EraserTool'
import { FloodFillTool } from '@/components/labeling/tools/FloodFillTool'
import { LassoTool } from '@/components/labeling/tools/LassoTool'
import { PolygonTool } from '@/components/labeling/tools/PolygonTool'

const toolInstances: Record<ToolName, BaseTool> = {
  'skin-brush': new BrushTool('skin-brush'),
  'lesion-brush': new BrushTool('lesion-brush'),
  'eraser': new EraserTool(),
  'flood-fill': new FloodFillTool(),
  'lasso': new LassoTool(),
  'polygon': new PolygonTool(),
  'grabcut': new EraserTool(), // placeholder — not available yet
}

export function useCanvasTools(allowedTools?: ToolName[]) {
  const whitelist = allowedTools && allowedTools.length > 0 ? new Set(allowedTools) : null
  const activeToolName = ref<ToolName>(
    whitelist ? [...whitelist][0] : 'lesion-brush',
  )
  const activeTool = computed<BaseTool>(() => toolInstances[activeToolName.value])
  const toolContext = shallowRef<ToolContext | null>(null)
  const availableTools = computed(() =>
    ALL_TOOLS.filter(t => t.available && (!whitelist || whitelist.has(t.name))),
  )

  function isAllowed(name: ToolName): boolean {
    const def = ALL_TOOLS.find(t => t.name === name)
    if (!def || !def.available) return false
    if (whitelist && !whitelist.has(name)) return false
    return true
  }

  function setTool(name: ToolName) {
    if (!isAllowed(name) || name === activeToolName.value) return

    // Deactivate current tool
    if (toolContext.value) {
      activeTool.value.onDeactivate()
    }

    activeToolName.value = name

    // Activate new tool
    if (toolContext.value) {
      activeTool.value.onActivate(toolContext.value)
    }
  }

  function setContext(ctx: ToolContext) {
    toolContext.value = ctx
    activeTool.value.onActivate(ctx)
  }

  /** Handle keyboard shortcuts for tool switching */
  function handleToolShortcut(key: string, _shiftKey: boolean): boolean {
    const upper = key.toUpperCase()
    const tool = ALL_TOOLS.find(t => t.shortcut === upper && isAllowed(t.name))
    if (tool) {
      setTool(tool.name)
      return true
    }

    // Number keys: quick switch to the Nth available tool
    if (upper >= '1' && upper <= '9') {
      const idx = Number(upper) - 1
      const toolDef = availableTools.value[idx]
      if (toolDef) {
        setTool(toolDef.name)
        return true
      }
    }

    return false
  }

  /** Get the flood fill tool instance for modifier-based fills */
  function getFloodFillTool(): FloodFillTool | null {
    if (!isAllowed('flood-fill')) return null
    const tool = toolInstances['flood-fill']
    return tool instanceof FloodFillTool ? tool : null
  }

  function onPointerDown(pos: [number, number]) {
    if (!toolContext.value) return
    activeTool.value.onPointerDown(pos, toolContext.value)
  }

  function onPointerMove(pos: [number, number]) {
    if (!toolContext.value) return
    activeTool.value.onPointerMove(pos, toolContext.value)
  }

  function onPointerUp() {
    if (!toolContext.value) return
    activeTool.value.onPointerUp(toolContext.value)
  }

  function onKeyDown(key: string) {
    if (!toolContext.value) return
    activeTool.value.onKeyDown(key, toolContext.value)
  }

  function getCursor(): string {
    return activeTool.value.getCursor()
  }

  return {
    activeToolName,
    activeTool,
    availableTools,
    toolContext,
    setTool,
    setContext,
    handleToolShortcut,
    getFloodFillTool,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onKeyDown,
    getCursor,
  }
}
