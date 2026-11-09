import { isCloud, isDesktop } from '@/platform/distribution/types'
import { normalizeI18nKey } from '@/utils/formatUtil'
import type { SettingParams } from '@/platform/settings/types'

const hiddenSettings = new Set([
  'Comfy.Execution.PreviewMethod',
  'Comfy.EditAttention.Delta',
  'Comfy.NodeBadge.ShowApiPricing',
  'Comfy.ModelLibrary.AutoLoadAll',
  'Comfy.ModelLibrary.NameFormat',
  'Comfy.ModelLibrary.UseAssetBrowser',
  'Comfy.Memory.AllowManualUnload',
  'Comfy.ErrorSystem.ShowMissingModels',
  'Comfy.Workflow.ShowMissingModelsWarning',
  'Comfy.NodeSearchBoxImpl.ShowNodeFrequency',
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

const hiddenLocalCommands = new Set([
  'Comfy.BrowseTemplates',
  'Comfy.User.OpenSignInDialog',
  'Comfy.User.SignOut',
  'Comfy.OpenClipspace',
  'Comfy.Memory.UnloadModels',
  'Comfy.Memory.UnloadModelsAndExecutionCache',
  'Comfy.Onboarding.Replay',
  'Comfy.OpenManagerDialog',
  'Comfy.ToggleHelpCenter',
  'Workspace.ToggleSidebarTab.model-library'
])

export function isWorkbenchCommandAvailable(id: string): boolean {
  return (
    isCloud ||
    isDesktop ||
    (!hiddenLocalCommands.has(id) && !id.startsWith('Comfy.Manager.'))
  )
}

export function isSettingCommandVisible(id: string): boolean {
  if (isCloud || isDesktop) return true
  return (
    isWorkbenchCommandAvailable(id) &&
    id !== 'Experimental.ToggleVueNodes' &&
    !id.startsWith('Comfy.MaskEditor.') &&
    (!id.startsWith('Comfy.Help.') || id === 'Comfy.Help.AboutComfyUI')
  )
}

export function isSettingPanelVisible(key: string): boolean {
  if (isCloud || isDesktop) return key !== 'workbench'
  return !hiddenPanels.has(key)
}
