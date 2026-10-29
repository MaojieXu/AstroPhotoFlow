import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

import WorkbenchSettings from '@ui/core/WorkbenchSettings.vue'
import { ApiClientError, createWorkbenchClient } from '@ui/core/client'
import type { ConfigState } from '@ui/core/contracts'
import { ApiClientError as DataApiClientError } from '@ui/modules/data/api/client'

const controls = {
  formItem: defineComponent({
    props: ['item', 'id', 'formValue'],
    emits: ['update:formValue'],
    template: `<div><span>{{ item.name }}<slot name="name-suffix" /></span><input :id="id" :name="id" :type="item.type === 'number' ? 'number' : 'text'" :value="formValue" @input="$emit('update:formValue', item.type === 'number' ? Number($event.target.value) : $event.target.value)" /></div>`
  }),
  button: defineComponent({ template: '<button><slot /></button>' }),
  input: defineComponent({
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: `<input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`
  })
}

function configuration(): ConfigState {
  const values = {
    host: '127.0.0.1',
    service_port: 31390,
    data_dir: 'data',
    allowed_origins: ['http://127.0.0.1:31388'],
    import_roots: [],
    file_workers: 2,
    preview_workers: 1
  }
  return {
    config_path: 'C:/isolated/config.toml',
    data_dir_absolute: 'C:/isolated/data',
    default_workspace: null,
    saved: structuredClone(values),
    effective: structuredClone(values),
    config_token: 'current',
    restart_required: false
  }
}

describe('workbench configuration', () => {
  it.each([{ roots: [] }, { roots: [{ id: 'night', path: 'D:/Images/原始素材' }] }])('hides configured import roots while retaining them when other settings are saved', async ({ roots }) => {
    const initial = configuration()
    initial.saved.import_roots = roots
    const refreshed = configuration()
    refreshed.saved.import_roots = [...roots, { id: 'later', path: 'E:/More images' }]
    refreshed.config_token = 'refreshed'
    const client = {
      selectDirectory: vi.fn(), restart: vi.fn(), restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValueOnce(initial).mockResolvedValue(refreshed),
      saveConfiguration: vi.fn().mockResolvedValue(refreshed)
    }
    const wrapper = mount(WorkbenchSettings, { props: { client, controls, translate: key => key } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('apfWorkbench.importRoots')
    expect(wrapper.text()).not.toContain('apfWorkbench.addRoot')
    expect(wrapper.find('[aria-label="apfWorkbench.rootId"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="apfWorkbench.rootPath"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="apfWorkbench.importRootDetails"]').exists()).toBe(false)
    await wrapper.findAll('button').find(button => button.text() === 'apfWorkbench.reload')!.trigger('click')
    await flushPromises()
    await wrapper.get('input[name="file_workers"]').setValue(4)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(client.saveConfiguration).toHaveBeenCalledWith(expect.objectContaining({
      config_token: 'refreshed', values: { ...refreshed.saved, file_workers: 4 }
    }))
    expect(client.restart).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('shares the original error class and preserves validation fields', async () => {
    expect(DataApiClientError).toBe(ApiClientError)
    const fetchApi = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'VALIDATION_ERROR',
            message: 'invalid',
            fields: [
              { path: 'values.file_workers', message: 'positive required' }
            ]
          },
          request_id: 'ce88796a-b7bb-488d-9f15-645d04a87be5'
        }),
        { status: 422 }
      )
    )
    await expect(
      createWorkbenchClient(fetchApi).getConfiguration()
    ).rejects.toMatchObject({
      fields: [{ path: 'values.file_workers', message: 'positive required' }]
    })
    expect(fetchApi).toHaveBeenCalledWith(
      '/astrophotoflow/api/v1/settings/workbench',
      undefined
    )
  })

  it('saves the edited value while displaying the unchanged effective value', async () => {
    const initial = configuration()
    const next = configuration()
    next.saved.file_workers = 4
    next.config_token = 'new'
    next.restart_required = true
    const client = {
      selectDirectory: vi.fn(),
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(initial),
      saveConfiguration: vi.fn().mockResolvedValue(next)
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, controls, translate: (key) => key }
    })
    await flushPromises()
    await wrapper.get('input[name="file_workers"]').setValue(4)
    expect(
      wrapper.get('[data-testid="workbench-restart"]').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.text()).toContain('apfWorkbench.saveFirst')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(client.saveConfiguration).toHaveBeenCalledWith({
      config_token: 'current',
      values: { ...initial.saved, file_workers: 4 }
    })
    expect(
      wrapper.get('[data-testid="effective-file-workers"]').text()
    ).toContain('2')
    expect(wrapper.get('[data-testid="configuration-state"]').text()).toBe(
      'apfWorkbench.restartRequired'
    )
    expect(wrapper.text()).toContain('http://127.0.0.1:31390')
    wrapper.unmount()
  })

  it('keeps user input after a conflict and does not silently reload or resubmit', async () => {
    const client = {
      selectDirectory: vi.fn(),
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(configuration()),
      saveConfiguration: vi
        .fn()
        .mockRejectedValue(
          new ApiClientError(
            'changed',
            'service',
            409,
            'CONFIGURATION_CONFLICT',
            'request-1'
          )
        )
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, controls, translate: (key) => key }
    })
    await flushPromises()
    await wrapper.get('input[name="file_workers"]').setValue(5)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(
      (wrapper.get('input[name="file_workers"]').element as HTMLInputElement)
        .value
    ).toBe('5')
    expect(wrapper.get('[role="alert"]').text()).toContain('request-1')
    expect(client.getConfiguration).toHaveBeenCalledTimes(1)
    expect(client.saveConfiguration).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('shows field errors without losing edits after validation fails', async () => {
    const client = {
      selectDirectory: vi.fn(),
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(configuration()),
      saveConfiguration: vi
        .fn()
        .mockRejectedValue(
          new ApiClientError(
            'invalid',
            'service',
            422,
            'INVALID_CONFIGURATION',
            'validation-request',
            [{ path: 'values.host', message: 'loopback required' }]
          )
        )
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, controls, translate: (key) => key }
    })
    await flushPromises()
    await wrapper.get('input[name="host"]').setValue('0.0.0.0')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'values.host: loopback required'
    )
    expect(
      (wrapper.get('input[name="host"]').element as HTMLInputElement).value
    ).toBe('0.0.0.0')
    expect(client.restart).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('selects folders into the form, preserves cancellation, and requires an explicit save', async () => {
    const client = {
      selectDirectory: vi
        .fn()
        .mockResolvedValueOnce('C:/workspace')
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce('D:/data'),
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(configuration()),
      saveConfiguration: vi.fn()
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, controls, translate: (key) => key }
    })
    await flushPromises()
    expect(
      wrapper.get('[data-testid="data-directory-hint"]').attributes('tooltip')
    ).toContain('C:/isolated/data')
    await wrapper
      .get('[aria-label="apfWorkbench.chooseWorkspace"]')
      .trigger('click')
    await flushPromises()
    expect(
      (
        wrapper.get('input[name="default_workspace"]')
          .element as HTMLInputElement
      ).value
    ).toBe('C:/workspace')
    await wrapper
      .get('[aria-label="apfWorkbench.chooseDataDirectory"]')
      .trigger('click')
    await flushPromises()
    expect(
      (wrapper.get('input[name="data_dir"]').element as HTMLInputElement).value
    ).toBe('data')
    await wrapper
      .get('[aria-label="apfWorkbench.chooseDataDirectory"]')
      .trigger('click')
    await flushPromises()
    expect(
      (wrapper.get('input[name="data_dir"]').element as HTMLInputElement).value
    ).toBe('D:/data')
    expect(client.selectDirectory.mock.calls).toEqual([
      [''],
      ['data'],
      ['data']
    ])
    expect(client.saveConfiguration).not.toHaveBeenCalled()
    expect(client.restart).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps full paths in hints and preserves saved status when a hint is clicked', async () => {
    const initial = configuration()
    initial.default_workspace = 'C:/a very long workspace/selected folder'
    initial.saved.import_roots = [
      { id: 'night', path: 'D:/raw inputs/very long night directory' }
    ]
    const client = {
      selectDirectory: vi.fn(),
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(initial),
      saveConfiguration: vi.fn().mockResolvedValue(initial)
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, controls, translate: (key) => key }
    })
    await flushPromises()
    expect(wrapper.text()).not.toContain(initial.config_path)
    expect(wrapper.text()).not.toContain(initial.data_dir_absolute)
    expect(wrapper.text()).not.toContain('apfWorkbench.defaultHelp')
    expect(wrapper.text()).not.toContain('apfWorkbench.saveHelp')
    expect(wrapper.text()).not.toContain('apfWorkbench.restartHelp')
    expect(wrapper.text()).toContain('http://127.0.0.1:31390')
    expect(
      wrapper
        .get('[aria-label="apfWorkbench.workspaceHelp"]')
        .attributes('tooltip')
    ).toContain(initial.default_workspace)
    expect(wrapper.find('[aria-label="apfWorkbench.importRootDetails"]').exists()).toBe(false)
    const hint = wrapper.get('[data-testid="data-directory-hint"]')
    expect(hint.attributes('tooltip')).toContain(initial.data_dir_absolute)
    expect(hint.attributes('tooltip')).not.toContain(
      'apfWorkbench.currentDataDirectory'
    )
    await wrapper.get('input[name="data_dir"]').setValue('D:/draft directory')
    expect(hint.attributes('tooltip')).toContain(
      'apfWorkbench.currentDataDirectory: D:/draft directory'
    )
    expect(hint.attributes('tooltip')).toContain(initial.data_dir_absolute)
    expect(client.saveConfiguration).not.toHaveBeenCalled()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('apfWorkbench.saved')
    await hint.trigger('click')
    expect(wrapper.text()).toContain('apfWorkbench.saved')
    expect(client.saveConfiguration).toHaveBeenCalledTimes(1)
    expect(client.saveConfiguration.mock.calls[0][0].values.import_roots).toEqual(initial.saved.import_roots)
    expect(client.restart).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('uses the fixed directory selection endpoint and preserves cancellation', async () => {
    const fetchApi = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ path: null })))
    expect(
      await createWorkbenchClient(fetchApi).selectDirectory('data')
    ).toBeNull()
    expect(fetchApi).toHaveBeenCalledWith(
      '/astrophotoflow/api/v1/settings/workbench/select-directory',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ path: 'data' })
      })
    )
  })

  it('shows missing adopted values without presenting saved addresses as current', async () => {
    const initial = configuration()
    initial.effective = null
    const client = {
      selectDirectory: vi.fn(),
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(initial),
      saveConfiguration: vi.fn()
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, controls, translate: (key) => key }
    })
    await flushPromises()
    expect(wrapper.text()).toContain('apfWorkbench.noRunningValues')
    expect(wrapper.find('dl').exists()).toBe(false)
    wrapper.unmount()
  })
  it.each(['completed', 'rejected'] as const)(
    'observes restart %s without resubmitting',
    async (state) => {
      const result = {
        operation_id: 'ce88796a-b7bb-488d-9f15-645d04a87be5',
        state,
        detail: null,
        blockers: state === 'rejected' ? ['busy import'] : []
      }
      const client = {
        selectDirectory: vi.fn(),
        getConfiguration: vi.fn().mockResolvedValue(configuration()),
        saveConfiguration: vi.fn(),
        restart: vi
          .fn()
          .mockRejectedValue(new ApiClientError('response lost', 'network')),
        restartResult: vi
          .fn()
          .mockRejectedValueOnce(new ApiClientError('offline', 'network'))
          .mockResolvedValue(result)
      }
      const wrapper = mount(WorkbenchSettings, {
        props: { client, controls, translate: (key) => key }
      })
      await flushPromises()
      expect(wrapper.get('a').attributes('href')).toBe('http://127.0.0.1:31388')
      vi.useFakeTimers()
      try {
        await wrapper.get('[data-testid="workbench-restart"]').trigger('click')
        expect(
          wrapper
            .get('[data-testid="workbench-restart"]')
            .attributes('disabled')
        ).toBeDefined()
        await vi.advanceTimersByTimeAsync(2000)
        expect(client.restart).toHaveBeenCalledTimes(1)
        expect(client.restartResult).toHaveBeenCalledTimes(2)
        if (state === 'rejected')
          expect(wrapper.get('[role="alert"]').text()).toContain('busy import')
        else expect(wrapper.text()).toContain('apfWorkbench.restarted')
      } finally {
        wrapper.unmount()
        vi.useRealTimers()
      }
    }
  )
})
