import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import CalibrationBindingsEditor from '@ui/modules/data/datasets/CalibrationBindingsEditor.vue'
import { ApiClientError } from '@ui/core/api/errors'

const api = vi.hoisted(() => ({
  get: vi.fn(), dataset: vi.fn(), calibrationTargets: vi.fn(), updateDataset: vi.fn()
}))
vi.mock('@ui/modules/data/api', () => ({datasetApi: api}))
vi.mock('@ui/modules/data/api/calibration', () => ({calibrationApi: api}))
const target = {kind: 'asset', id: 'master'}

it('saves the current dataset slot and confirms specific unknowns', async () => {
  let revision = 1
  api.dataset.mockImplementation(async () => ({
    revision,
    calibration: {flat: revision === 1 ? {mode: 'unconfigured'} : {mode: 'target', target}},
    slots: {}
  }))
  api.calibrationTargets.mockResolvedValue({items: [{frame_type: 'flat', target, name: 'Master Flat', calibration_status:'Unknown',calibration_counts:{UnCalibrated:0,Calibrated:0,Unknown:1},member_count: 1}], total: 1})
  api.updateDataset.mockRejectedValueOnce(new ApiClientError('Unknown', 'service', 409, 'CALIBRATION_UNKNOWN'))
    .mockImplementationOnce(async () => {
      revision = 2
      return {result: {dataset_id: 'group', revision: 2, calibration_status:'Unknown',calibration_counts:{UnCalibrated:0,Calibrated:0,Unknown:1},member_count: 1}}
    })
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const wrapper = mount(CalibrationBindingsEditor, {props: {workspaceId: 'test', datasetId: 'group'}})
  try {
    const details = wrapper.get('details')
    ;(details.element as HTMLDetailsElement).open = true
    await details.trigger('toggle')
    await flushPromises()
    const flat = wrapper.findAll('select').find(select => select.html().includes('Master Flat'))!
    await flat.setValue('asset:master')
    await wrapper.findAll('button').at(-1)!.trigger('click')
    await flushPromises()
    const expected = {expected_revision: 1, changes: {flat: {mode: 'target', target}}}
    expect(api.updateDataset).toHaveBeenNthCalledWith(1, 'group', expect.objectContaining(expected))
    expect(api.updateDataset).toHaveBeenNthCalledWith(2, 'group', expect.objectContaining({...expected, accept_unknown: true}))
    expect(wrapper.text()).toContain('已保存数据集校准设置')
  } finally {
    confirm.mockRestore()
    wrapper.unmount()
  }
})
