import { computed, shallowRef, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { ProjectOut } from '../../../generated/api/types.gen'
import type { Equipment } from '../api/contracts'
import type { EquipmentDraft } from '../equipment/drafts'
import type { ProjectEditorDraft, RecordEditorState } from './editorTypes'
import { specFields, specValue } from '../equipment/fields'
import { useCreateProject } from '../projects/mutations'
import { useCreateEquipment, useUpdateEquipment } from '../equipment/mutations'
import { validatedInput } from '../../../core/api/input'
import { zProjectOut, zEquipmentPage, zCreateProjectApiV1ProjectsPostBody, zCreateEquipmentApiV1EquipmentPostBody, zPatchEquipmentApiV1EquipmentEquipmentIdPatchBody } from '../../../generated/api/zod.gen'

type Session =
  | { kind: 'project'; source?: ProjectOut; draft: ProjectEditorDraft; original: ProjectEditorDraft }
  | { kind: 'equipment'; source?: Equipment; draft: EquipmentDraft; original: EquipmentDraft }

function text(value: string | null | undefined): string { return value ?? '' }
function nullable(value: string | null | undefined) { return value === '' ? null : value }
function inputNumber(value: unknown) {
  if (value === '' || value == null) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function useRecordEditor(workspace: MaybeRefOrGetter<string>) {
  const projectWrite=useCreateProject(),createEquipment=useCreateEquipment(),updateEquipment=useUpdateEquipment()
  const session = shallowRef<Session>()
  const model = computed<RecordEditorState | undefined>({
    get: (): RecordEditorState | undefined => {
      const current = session.value
      if (current?.kind === 'project') return { kind: 'project', id: current.source?.id, draft: current.draft }
      if (current?.kind === 'equipment') return { kind: 'equipment', id: current.source?.id, draft: current.draft }
      return undefined
    },
    set: (value: RecordEditorState | undefined) => {
      const current = session.value
      if (!current || !value || current.kind !== value.kind || current.source?.id !== value.id) return
      if (current.kind === 'project' && value.kind === 'project') session.value = { ...current, draft: value.draft }
      else if (current.kind === 'equipment' && value.kind === 'equipment') session.value = { ...current, draft: value.draft }
    }
  })
  const dirty = computed(() => Boolean(session.value && JSON.stringify(session.value.draft) !== JSON.stringify(session.value.original)))
  const source = computed(() => session.value?.source)

  function project(record?: ProjectOut) {
    const draft: ProjectEditorDraft = { name: record?.name ?? '', target_name: text(record?.target_name), notes: text(record?.notes) }
    session.value = { kind: 'project', source: record, draft, original: structuredClone(draft) }
  }
  function equipment(record?: Equipment) {
    const kind = record?.kind ?? 'camera'
    const draft: EquipmentDraft = { kind, name: record?.name ?? '', model: text(record?.model),
      notes: text(record?.notes), specs: record ? { ...record.specs } : Object.fromEntries(specFields[kind].map(field => [field.key, null])) }
    session.value = { kind: 'equipment', source: record, draft, original: structuredClone(draft) }
  }
  function synchronize(id: string, value: unknown) {
    const current = session.value
    if (!current?.source || current.source.id !== id) return
    if (current.kind === 'project') project(zProjectOut.parse(value))
    else equipment(zEquipmentPage.shape.items.element.parse(value))
  }
  async function submit() {
    const current = session.value
    if (!current) throw new Error('No record editor is open')
    if (current.kind === 'project') {
      if (current.source) throw new Error('Existing projects use explicit field saves')
      return projectWrite.mutateAsync({workspaceId:toValue(workspace),body:validatedInput(zCreateProjectApiV1ProjectsPostBody, {
        name: current.draft.name, target_name: nullable(current.draft.target_name), notes: nullable(current.draft.notes)
      })})
    }
    const { draft, original } = current
    if (current.source) {
      const payload: Record<string, unknown> = { kind: draft.kind, base_revision: current.source.revision }
      for (const key of ['name', 'model', 'notes'] as const)
        if (draft[key] !== original[key]) payload[key] = key === 'name' ? draft[key] : nullable(draft[key])
      const specs = Object.fromEntries(Object.entries(draft.specs).filter(([key, value]) => value !== original.specs[key]))
      if (Object.keys(specs).length) payload.specs = specs
      return updateEquipment.mutateAsync({workspaceId:toValue(workspace),equipmentId:current.source.id,body:validatedInput(zPatchEquipmentApiV1EquipmentEquipmentIdPatchBody, payload)})
    }
    const specs = Object.fromEntries(specFields[draft.kind].map(field => [field.key,
      field.type ? inputNumber(specValue(field, draft.specs)) : draft.specs[field.key] === '' ? null : draft.specs[field.key]]))
    if (draft.kind === 'telescope') specs.optical_accessories = draft.specs.optical_accessories ?? []
    return createEquipment.mutateAsync({workspaceId:toValue(workspace),body:validatedInput(zCreateEquipmentApiV1EquipmentPostBody, {
      kind: draft.kind, name: draft.name, model: nullable(draft.model), notes: nullable(draft.notes), specs
    })})
  }
  return { model, dirty, source, project, equipment, synchronize, submit, close: () => { session.value = undefined } }
}
