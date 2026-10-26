import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { ApiClientError } from '@ui/modules/data/api/client'
import ImportTasks from '@ui/modules/data/workspace/ImportTasks.vue'
import { taskSchema } from '@ui/modules/data/api/contracts'

const { get, send } = vi.hoisted(() => ({
  get: vi.fn(),
  send: vi.fn()
}))

vi.mock('@ui/modules/data/api/index', () => ({
  assetApi: { get, send }
}))

const taskId = 'e7607462-d243-4cc2-a39f-0385755b5c08'
const baseTask = taskSchema.parse({
  id: taskId,
  status: 'interrupted',
  sources: [],
  storage_mode: 'reference',
  classification: {},
  parameters: {},
  notes: null,
  dataset_name: null,
  target_dataset_id: null,
  dataset_base_revision: null,
  dataset_id: null,
  enumeration_completed: true,
  retry_of_task_id: null,
  report: {},
  error: { code: 'SERVICE_INTERRUPTED', message: 'service stopped' },
  created_at: '2026-10-22T20:00:00Z',
  updated_at: '2026-10-22T20:00:01Z',
  items: [],
  items_total: 4,
  items_completed: 2,
  items_limit: 20,
  items_offset: 0
})
const taskPage = (task: ReturnType<typeof taskSchema.parse>) => ({ items: [task], total: 1, limit: 50, offset: 0 })

let wrapper: ReturnType<typeof mount> | undefined

beforeEach(() => {
  get.mockReset()
  send.mockReset()
  get.mockResolvedValue(taskPage(baseTask))
  send.mockResolvedValue({ task_id: taskId, status: 'queued' })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
})

describe('inline import progress', () => {
  it('shows only progress for a persisted interrupted import', async () => {
    wrapper = mount(ImportTasks, { props: { refreshToken: 0 } })
    await flushPromises()

    const progress = wrapper.get('progress')
    expect(progress.attributes('value')).toBe('50')
    expect(wrapper.text()).toContain('已暂停，进度已保存')
    expect(wrapper.text()).toContain('2 / 4 项已处理')
    expect(wrapper.text()).not.toContain('后台任务')
    expect(wrapper.text()).not.toContain('数据集')
    expect(wrapper.text()).not.toContain('Gain')
    expect(wrapper.text()).not.toContain('参数')
  })

  it('uses indeterminate progress while the source folder is still being enumerated', async () => {
    get.mockResolvedValue(taskPage({
      ...baseTask,
      status: 'running',
      enumeration_completed: false,
      items_completed: 1
    }))
    wrapper = mount(ImportTasks, { props: { refreshToken: 0 } })
    await flushPromises()

    expect(wrapper.get('progress').attributes('value')).toBeUndefined()
    expect(wrapper.text()).toContain('1 项已处理，正在读取剩余来源')
  })

  it('offers resume for a persisted interrupted task', async () => {
    const resumed = { ...baseTask, status: 'queued' as const, error: null }
    get.mockResolvedValueOnce(taskPage(baseTask)).mockResolvedValue(taskPage(resumed))
    wrapper = mount(ImportTasks, { props: { refreshToken: 0 } })
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(send).toHaveBeenCalledWith(
      '/astrophotoflow/api/v1/asset-tasks/' + taskId + '/resume',
      expect.anything(),
      'POST',
      {}
    )
    expect(wrapper.text()).toContain('正在导入')
  })

  it('passes task recovery errors into the workspace slot', async () => {
    send.mockRejectedValue(new ApiClientError('上传未完成，请重新选择文件创建导入批次。', 'service', 409, 'UPLOAD_REQUIRES_SELECTION'))
    wrapper = mount(ImportTasks, {
      props: { refreshToken: 1 },
      slots: { default: ({ error, tasks, resume }: { error: string; tasks: ReturnType<typeof taskSchema.parse>[]; resume: (task: ReturnType<typeof taskSchema.parse>)=>Promise<void> }) => h('div', [
        h('p', { role: 'alert' }, error),
        h('button', { onClick: () => resume(tasks[0]) }, '恢复')
      ]) }
    })
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('请重新选择文件')
  })

  it('refreshes library when an import completed before the first poll', async () => {
    get.mockResolvedValue(taskPage({...baseTask,status:'completed'}))
    wrapper=mount(ImportTasks,{props:{refreshToken:1,watchTaskIds:[taskId]}})
    await flushPromises()
    expect(wrapper.emitted('completed')).toEqual([[taskId]])
  })

  it('switches from uploaded-byte progress to processing progress', async () => {
    get.mockResolvedValue(taskPage({
      ...baseTask,status:'running',report:{upload_manifest:true,upload_complete:true,upload_files:[]},
      items_total:5,items_completed:0
    }))
    wrapper=mount(ImportTasks,{props:{
      refreshToken:1,uploadProgress:{[taskId]:{loaded:100,total:100}}
    }})
    await flushPromises()
    expect(wrapper.get('progress').attributes('value')).toBe('0')
    expect(wrapper.text()).toContain('0 / 5 项已处理')
  })
})
