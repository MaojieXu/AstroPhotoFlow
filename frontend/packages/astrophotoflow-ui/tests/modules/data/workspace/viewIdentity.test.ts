import { describe, expect, it } from 'vitest'
import { datasetViewFromSummary, datasetViewFromAcknowledgement } from '@ui/modules/data/datasets/viewIdentity'
import { observedEquipmentChoices } from '@ui/modules/data/equipment/snapshots'
import type { DatasetOut, EquipmentSnapshots, LibraryDatasetSummary } from '@ui/generated/api/types.gen'
import { metadataForMembers } from '../../../fixtures/library-summary'

const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
describe('current view identities and observed equipment choices', () => {
  it('reads dataset identity and adopts the acknowledged current metadata', () => {
    const summary: LibraryDatasetSummary = { entry_type: 'dataset', id: id(1), name: 'Group', notes: null,
      status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z',
      calibration_status: 'Unknown', calibration_counts: {UnCalibrated:0,Calibrated:0,Unknown:0}, member_count: 0, exposure_summary: {subframe_count:0,known_count:0,unknown_count:0,total_seconds:null,complete:true}, matching_member_count: 0, input_ready: false, summary: metadataForMembers([]), thumbnail: null, import_issue: null }
    const opened = datasetViewFromSummary(summary)!
    summary.member_count = 10
    expect(opened.member_count).toBe(0)
    const acknowledged: DatasetOut = { id: id(1), name: 'Group', notes: null, status: 'active', revision: 2,
      calibration_status: 'Unknown', calibration_counts: {UnCalibrated:0,Calibrated:0,Unknown:10}, member_count: 10, exposure_summary: {subframe_count:10,known_count:0,unknown_count:10,total_seconds:null,complete:false}, summary: summary.summary, input_ready: true,
      created_at: summary.created_at, updated_at: summary.created_at }
    expect(datasetViewFromAcknowledgement(acknowledged)).toEqual({id:id(1),name:'Group',revision:2,member_count:10})
  })

  it('keeps an observed telescope intact while projecting its optical selection slot', () => {
    const snapshots: EquipmentSnapshots = { optical_system_id: { kind: 'telescope', id: id(4), name: 'Observed optics', specs: {} } }
    expect(observedEquipmentChoices(snapshots)).toEqual([{ kind: 'optical_system', id: id(4), name: 'Observed optics' }])
    expect(snapshots.optical_system_id?.kind).toBe('telescope')
    expect(snapshots.optical_system_id?.name).toBe('Observed optics')
  })
})
