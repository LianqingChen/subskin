/**
 * useCanvasTools — manages the active tool, tool switching, and tool lifecycle.
 *
 * Owns the tool instances and provides keyboard-shortcut-based switching.
 */

import { ref, computed, shallowRef } from 'vue'
import type { BaseTool, ToolContext, ToolDef, ToolName } from '@/components/labeling/tools/BaseTool'
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

export function useCanvasTools() {
  const activeToolName = ref<ToolName>('lesion-brush')
  const activeTool = computed<BaseTool>(() => toolInstances[activeToolName.value])
  const toolContext = shallowRef<ToolContext | null>(null)
  const availableTools = computed(() => ALL_TOOLS.filter(t => t.available))

  function setTool(name: ToolName) {
    if (!ALL_TOOLS.find(t => t.name === name)?.available) return

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
  function handleToolShortcut(key: string, shiftKey: boolean): boolean {
    const upper = key.toUpperCase()
    const tool = ALL_TOOLS.find(t => t.shortcut === upper && t.available)
    if (tool) {
      // Shift+L = skin brush, L = lesion brush (convenience aliases)
      // B always = skin brush, L always = lesion brush
      setTool(tool.name)
      return true
    }

    // Number keys: quick switch
    const numMap: Record<string, ToolName> = {
      '1': 'skin-brush',
      '2': 'lesion-brush',
      '3': 'flood-fill',
      '4': 'lasso',
      '5': 'polygon',
      '6': 'eraser',
    }
    if (numMap[upper]) {
      setTool(numMap[upper])
      return true
    }

    return false
  }

  /** Get the flood fill tool instance for modifier-based fills */
  function getFloodFillTool(): FloodFillTool | null {
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
