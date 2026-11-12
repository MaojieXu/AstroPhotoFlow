import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import SettingsPage from '@ui/modules/data/library/SettingsPage.vue'
import AssetDetails from '@ui/modules/data/assets/AssetDetails.vue'
import DatasetDetails from '@ui/modules/data/datasets/DatasetDetails.vue'
import InlineField from '@ui/modules/data/components/InlineField.vue'
import type { AssetOut, DatasetOut } from '@ui/generated/api/types.gen'
import type { AssetDetailBindings } from '@ui/modules/data/assets/detailTypes'
import { assetFixture } from '../../../fixtures/library-members'
import { metadataForMembers } from '../../../fixtures/library-summary'

const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
const asset: AssetOut = assetFixture({ id: id(1), name: 'Light.fit', scope: 'shared', owner_project_id: null, role: 'raw', calibration_level: null,
  classification: { frame_class: 'subframe', frame_type: 'light' },
  parameters: { parameter_mode: 'gain', gain: 0, offset: 0, exposure_seconds: 0, binning_x: 2, binning_y: 1 },
  equipment_snapshot: {}, value_sources: {}, notes: null, status: 'active', revision: 1,
  created_at: '2026-10-28T12:00:00Z' })

describe('settings detail boundaries without a Workspace provider', () => {
  it('keeps a displayed project reference and delegates its action with the reference identity', async () => {
    const wrapper = mount(SettingsPage, {
      props: { workspaceId: '/fixture', projectMode: 'dataset-references', choosing: false, details: {
        recordId: id(2), title: 'Fixed group', subtitle: ''
      } }, global: { stubs: { WorkspaceRecords: true } }
    })
    try {
      await wrapper.findAll('button').find(button => button.text() === '从项目移除图像组')!.trigger('click')
      expect(wrapper.emitted('reference-action')).toEqual([[id(2), 'dataset-references', false]])
    } finally { wrapper.unmount() }
  })

  it('retains zero values, snapshot labels and the record identity when cancelling an asset edit', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const bindings: AssetDetailBindings = { calibration_status: save, calibration_reason: save, name: save, frame_class: save, frame_type: save, camera_id: save,
      optical_system_id: save, filter_id: save, exposure_seconds: save, integration_seconds: save,
      sensor_temperature_c: save, cfa_pattern: save, status: save, notes: save, parameters: save, binning: save }
    const control = { display: 'Imported camera snapshot', choices: [], message: '' }
    const wrapper = mount(AssetDetails, { props: { asset, recordId: id(4), title: asset.name, bindings,
      equipment: { camera_id: control, optical_system_id: control, filter_id: control },
      binning: { value: 'legacy:2x1', display: 'Bin2×1', choices: [] }, temperatureDisplay: '—' } })
    try {
      expect(wrapper.text()).toContain('Gain · 0')
      expect(wrapper.text()).toContain('Offset · 0')
      expect(wrapper.text()).toContain('Imported camera snapshot')
      expect(wrapper.text()).toContain('Bin2×1')
      expect(wrapper.findAllComponents(InlineField).some(field => field.props('value') === 0)).toBe(true)
      await wrapper.get('.apf-inline-value').trigger('dblclick')
      await flushPromises()
      await wrapper.get('input').trigger('keydown', { key: 'Escape' })
      expect(wrapper.emitted('cancel-field')).toEqual([['name', id(4)]])
      expect(save).not.toHaveBeenCalled()
    } finally { wrapper.unmount() }
  })

  it('keeps dataset edits associated with the reference rather than replacing its identity with the dataset id', async () => {
    const dataset: DatasetOut = { id: id(5), name: 'Group', notes: null, status: 'active', revision: 1,
      calibration_status: 'Unknown', calibration_counts: {UnCalibrated:0,Calibrated:0,Unknown:0}, member_count: 0, exposure_summary: {subframe_count:0,known_count:0,unknown_count:0,total_seconds:null,complete:true}, summary: metadataForMembers([]), input_ready: false,
      created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' }
    const save = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(DatasetDetails, { props: { dataset, recordId: id(7), saveName: save, saveStatus: save, saveNotes: save } })
    try {
      await wrapper.get('.apf-inline-value').trigger('dblclick')
      await flushPromises()
      await wrapper.get('input').trigger('keydown', { key: 'Escape' })
      expect(wrapper.emitted('cancel-field')).toEqual([['name', id(7)]])
      expect(dataset.id).toBe(id(5))
    } finally { wrapper.unmount() }
  })
})
