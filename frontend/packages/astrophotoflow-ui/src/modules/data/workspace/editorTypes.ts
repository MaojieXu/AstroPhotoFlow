import type { ProjectCreate } from '../../../generated/api/types.gen'
import type { EquipmentDraft } from '../equipment/drafts'

export type ProjectEditorField = 'name' | 'target_name' | 'notes'
export type ProjectEditorDraft = Pick<ProjectCreate, ProjectEditorField>
export type RecordEditorState =
  | { kind: 'project'; id?: string; draft: ProjectEditorDraft }
  | { kind: 'equipment'; id?: string; draft: EquipmentDraft }
