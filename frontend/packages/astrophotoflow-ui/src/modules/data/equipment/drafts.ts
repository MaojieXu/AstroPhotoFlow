import type { EquipmentSetupCreate } from '../../../generated/api/types.gen'

type ComponentInput = NonNullable<EquipmentSetupCreate['components']>[number]
type InlineInput = Extract<ComponentInput, { source: 'inline' }>['equipment']

// Editable controls hold unvalidated values; submitted/output DTOs remain generated.
export type EquipmentDraft = Omit<InlineInput, 'specs'> & {
  specs: Record<string, unknown>
}
export type SetupComponentDraft =
  | Extract<ComponentInput, { source: 'registered' }>
  | (Omit<Extract<ComponentInput, { source: 'inline' }>, 'equipment'> & {
      equipment: EquipmentDraft
    })
