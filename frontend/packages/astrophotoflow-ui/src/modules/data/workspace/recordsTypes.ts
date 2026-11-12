import type LibraryTable from '../library/LibraryTable.vue'
import type DatasetReferenceTable from '../datasets/DatasetReferenceTable.vue'
import type ProjectCards from '../projects/ProjectCards.vue'
import type EquipmentCards from '../equipment/EquipmentCards.vue'
import type EquipmentSetupTable from '../equipment/EquipmentSetupTable.vue'
import type ImportTasks from '../imports/ImportTasks.vue'
import type RecordsFeedback from './RecordsFeedback.vue'
import type RecordsPagination from './RecordsPagination.vue'

export type RecordsBody =
  | { kind: 'library'; props: InstanceType<typeof LibraryTable>['$props'] }
  | { kind: 'datasets'; props: InstanceType<typeof DatasetReferenceTable>['$props'] }
  | { kind: 'projects'; props: InstanceType<typeof ProjectCards>['$props'] }
  | { kind: 'equipment'; props: InstanceType<typeof EquipmentCards>['$props'] }
  | { kind: 'setups'; props: InstanceType<typeof EquipmentSetupTable>['$props'] }
  | { kind: 'none' }
export interface RecordsPresentation {
  imports?: InstanceType<typeof ImportTasks>['$props']
  feedback: InstanceType<typeof RecordsFeedback>['$props']
  body: RecordsBody
  pagination: InstanceType<typeof RecordsPagination>['$props']
  previewUnavailable: boolean
}
