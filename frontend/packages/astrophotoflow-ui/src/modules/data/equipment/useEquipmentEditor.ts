import { toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { EquipmentPage } from '../../../generated/api/types.gen'
import { zPatchEquipmentApiV1EquipmentEquipmentIdPatchBody } from '../../../generated/api/zod.gen'
import { validatedInput } from '../../../core/api/input'
import { specFields } from './fields'
import { useUpdateEquipment } from './mutations'

export function useEquipmentEditor(workspaceId: MaybeRefOrGetter<string>) {
  const write = useUpdateEquipment()
  async function saveField(
    equipment: EquipmentPage['items'][number],
    field: string,
    value: string | number | null
  ) {
    const spec = field.startsWith('specs.')
      ? specFields[equipment.kind]?.find((item) => item.key === field.slice(6))
      : undefined
    const next =
      spec?.type === 'number'
        ? value == null || value === ''
          ? null
          : Number(value)
        : value
    const payload = field.startsWith('specs.')
      ? {
          base_revision: equipment.revision,
          kind: equipment.kind,
          specs: { [field.slice(6)]: next }
        }
      : {
          base_revision: equipment.revision,
          kind: equipment.kind,
          [field]: next
        }
    return write.mutateAsync({
      workspaceId: toValue(workspaceId),
      equipmentId: equipment.id,
      body: validatedInput(
        zPatchEquipmentApiV1EquipmentEquipmentIdPatchBody,
        payload
      )
    })
  }
  return { saveField, pending: write.isPending }
}
