import { isCloud, isDesktop } from '@/platform/distribution/types'
import { normalizeI18nKey } from '@/utils/formatUtil'
import type { SettingParams } from '@/platform/settings/types'

const hiddenSettings = new Set([
  'Comfy.Execution.PreviewMethod',
  'Comfy.EditAttention.Delta',
  'Comfy.NodeBadge.ShowApiPricing',
  'Comfy.ModelLibrary.AutoLoadAll',
  'Comfy.ModelLibrary.NameFormat',
  'Comfy.VueNodes.Enabled',
  'Comfy.NodeLibrary.NewDesign',
  'Comfy.UseNewMenu',
  'Comfy.NodeSearchBoxImpl',
  'Comfy.Queue.QPOV2',
  'Comfy.Notification.ShowVersionUpdates',
  'Comfy.DevMode',
  'Comfy.Workflow.SortNodeIdOnSave',
  'Comfy.Workflow.NamedValuesRestore',
  'Comfy.Graph.DeduplicateSubgraphNodeIds',
  'Comfy.Node.ShowExperimental',
  'Comfy.Node.ShowDeprecated'
])

const hiddenPanels = new Set([
  'user',
  'credits',
  'workspace',
  'workspace-members',
  'workspace-allowlist',
  'secrets',
  'skill-packs',
  'extension'
])

export function isSettingVisible(setting: SettingParams): boolean {
  return (
    isCloud ||
    isDesktop ||
    (!hiddenSettings.has(setting.id) &&
      !['3D', 'Mask Editor'].includes(
        (setting.category || setting.id.split('.'))[0]
      ))
  )
}

const advancedSettings = new Set([
  'Comfy.DisableFloatRounding',
  'Comfy.FloatRoundingPrecision',
  'LiteGraph.Canvas.MaximumFps',
  'LiteGraph.Canvas.MinFontSizeForLOD',
  'Comfy.DOMClippingEnabled',
  'Comfy.Pointer.ClickDrift',
  'Comfy.Pointer.DoubleClickTime',
  'LiteGraph.Reroute.SplineOffset'
])

export function isAdvancedSetting(setting: SettingParams): boolean {
  return !isCloud && !isDesktop && advancedSettings.has(setting.id)
}

export function settingCategoryLabelKey(category: string): string {
  const labels: Record<string, string> = {
    Comfy: 'general',
    LiteGraph: 'canvas',
    About: 'about'
  }
  return !isCloud && !isDesktop && labels[category]
    ? 'apfSettings.' + labels[category]
    : 'settingsCategories.' + normalizeI18nKey(category)
}

export function isSettingCommandVisible(id: string): boolean {
  return (
    isCloud ||
    isDesktop ||
    !(
      id === 'Comfy.BrowseTemplates' ||
      id === 'Experimental.ToggleVueNodes' ||
      id === 'Comfy.OpenManagerDialog' ||
      id === 'Comfy.ToggleHelpCenter' ||
      id.startsWith('Comfy.MaskEditor.') ||
      id.startsWith('Comfy.Manager.') ||
      (id.startsWith('Comfy.Help.') && id !== 'Comfy.Help.AboutComfyUI')
    )
  )
}

export function isSettingPanelVisible(key: string): boolean {
  if (isCloud || isDesktop) return key !== 'workbench'
  return !hiddenPanels.has(key)
}
