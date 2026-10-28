import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import WorkbenchSettings from '@ui/core/WorkbenchSettings.vue'
import { ApiClientError, createWorkbenchClient } from '@ui/core/client'
import type { ConfigState } from '@ui/core/contracts'
import { ApiClientError as DataApiClientError } from '@ui/modules/data/api/client'

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
    default_workspace: null,
    saved: structuredClone(values),
    effective: structuredClone(values),
    config_token: 'current',
    restart_required: false
  }
}

describe('workbench configuration', () => {
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
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(initial),
      saveConfiguration: vi.fn().mockResolvedValue(next)
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, translate: (key) => key }
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
      props: { client, translate: (key) => key }
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

  it('shows missing adopted values without presenting saved addresses as current', async () => {
    const initial = configuration()
    initial.effective = null
    const client = {
      restart: vi.fn(),
      restartResult: vi.fn(),
      getConfiguration: vi.fn().mockResolvedValue(initial),
      saveConfiguration: vi.fn()
    }
    const wrapper = mount(WorkbenchSettings, {
      props: { client, translate: (key) => key }
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
        props: { client, translate: (key) => key }
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
