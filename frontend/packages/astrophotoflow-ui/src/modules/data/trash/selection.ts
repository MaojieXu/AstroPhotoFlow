import type { EquipmentPage, EquipmentSetupOut, ProjectOut } from '../../../generated/api/types.gen'
import { zEquipmentPage, zEquipmentSetupOut, zProjectOut } from '../../../generated/api/zod.gen'

// A selection retains the reviewed identity and revision, not a copy of query data.
export type ManagementSelectionEntry =
  | { section: 'projects'; entry_type: 'project'; reference: Pick<ProjectOut, 'id' | 'revision' | 'name'> }
  | { section: 'equipment'; entry_type: 'equipment'; reference: Pick<EquipmentPage['items'][number], 'id' | 'revision' | 'name'> }
  | { section: 'equipment-setups'; entry_type: 'equipment_setup'; reference: Pick<EquipmentSetupOut, 'id' | 'revision' | 'name'> }

export type ManagementArchiveConfirmation =
  | { kind: 'single'; entry: ManagementSelectionEntry }
  | { kind: 'selection'; entries: readonly ManagementSelectionEntry[] }

function reference({ id, revision, name }: ManagementSelectionEntry['reference']) {
  return { id, revision, name }
}

export function managementSelectionEntry(section: string, value: unknown): ManagementSelectionEntry {
  switch (section) {
    case 'projects':
      return { section, entry_type: 'project', reference: reference(zProjectOut.parse(value)) }
    case 'equipment':
      return { section, entry_type: 'equipment', reference: reference(zEquipmentPage.shape.items.element.parse(value)) }
    case 'equipment-setups':
      return { section, entry_type: 'equipment_setup', reference: reference(zEquipmentSetupOut.parse(value)) }
    default:
      throw new TypeError(`Not a management resource: ${section}`)
  }
}

export function managementArchiveItems(entries: readonly ManagementSelectionEntry[]) {
  return entries.map(({ entry_type, reference: { id, revision } }) => ({ entry_type, id, revision }))
}

export function equipmentDeletionItems(entries: readonly ManagementSelectionEntry[]) {
  return entries.map(({ entry_type, reference: { id, revision } }) => {
    if (entry_type === 'project') throw new TypeError('Projects require project archive confirmation')
    return { entry_type, id, revision }
  })
}
