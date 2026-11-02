import type { EquipmentSnapshots, LibraryEquipmentLabel, LibraryMetadataSummary } from '../../../generated/api/types.gen'

export type EquipmentChoiceSnapshot = LibraryEquipmentLabel & { kind: 'camera' | 'optical_system' | 'filter' }

export function summaryEquipmentChoices(summary: LibraryMetadataSummary): EquipmentChoiceSnapshot[] {
  return ([['camera', 'camera'], ['optical_system', 'optical_system'], ['filter', 'filter']] as const)
    .flatMap(([slot, kind]) => summary[slot].value ? [{ ...summary[slot].value, kind }] : [])
}

export function observedEquipmentChoices(snapshots: EquipmentSnapshots): EquipmentChoiceSnapshot[] {
  const choices: EquipmentChoiceSnapshot[] = []
  if (snapshots.camera_id) choices.push({ kind: 'camera', id: snapshots.camera_id.id ?? null, name: snapshots.camera_id.name })
  // Both registered optical kinds occupy the same optical-system selection slot.
  if (snapshots.optical_system_id) choices.push({ kind: 'optical_system', id: snapshots.optical_system_id.id ?? null, name: snapshots.optical_system_id.name })
  if (snapshots.filter_id) choices.push({ kind: 'filter', id: snapshots.filter_id.id ?? null, name: snapshots.filter_id.name })
  return choices
}
