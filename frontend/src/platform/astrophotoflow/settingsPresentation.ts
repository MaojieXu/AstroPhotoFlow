import { isCloud, isDesktop } from '@/platform/distribution/types'
import type { SettingParams } from '@/platform/settings/types'

const hiddenSettings = new Set([
  'Comfy.Execution.PreviewMethod',
  'Comfy.EditAttention.Delta',
  'Comfy.NodeBadge.ShowApiPricing',
  'Comfy.ModelLibrary.AutoLoadAll',
  'Comfy.ModelLibrary.NameFormat'
])

const hiddenPanels = new Set([
  'user',
  'credits',
  'workspace',
  'workspace-members',
  'workspace-allowlist',
  'secrets',
  'skill-packs'
])

export function isSettingVisible(setting: SettingParams): boolean {
  return (
    isCloud ||
    isDesktop ||
    (!hiddenSettings.has(setting.id) &&
      (setting.category || setting.id.split('.'))[0] !== '3D')
  )
}

export function isSettingPanelVisible(key: string): boolean {
  if (isCloud || isDesktop) return key !== 'workbench'
  return !hiddenPanels.has(key)
}
