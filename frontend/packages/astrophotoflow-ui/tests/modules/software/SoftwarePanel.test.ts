import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SoftwarePanel from '@ui/modules/software/SoftwarePanel.vue'
import { ApiClientError } from '@ui/core/client'
import type { SoftwareClient } from '@ui/modules/software/api/client'
import type { PendingSoftwareAction, SoftwarePackage, SoftwarePackageDetails } from '@ui/modules/software/api/contracts'

const packageInfo: SoftwarePackage = {
  package_id: 'siril',
  name: 'Siril CLI',
  available_versions: ['1.4.4'],
  installed_version: null,
  install_path: null,
  package_token: 'package-token',
  availability: 'not_installed',
  reason: 'Not installed',
  operation: null,
  operation_state: 'idle',
  phase: null,
  progress: null,
  last_error: null,
  node_definition_ids: []
}

const pending: PendingSoftwareAction = {
  operation_id: '11111111-1111-4111-8111-111111111111',
  state: 'awaiting_confirmation',
  plan: {
    action: 'install',
    package_id: 'siril',
    current_version: null,
    target_version: '1.4.4',
    source: 'https://free-astro.org/download/siril-1.4.4-ucrt64_win.zip',
    install_path: 'C:/workspace/software/siril/app',
    package_token: 'package-token',
    impact_token: null,
    restart_required: null,
    restart_reason: 'B42 verification pending',
    node_changes: [],
    workflow_impacts: []
  },
  confirmation_url: 'http://127.0.0.1:8188/#/workflows?apf_panel=software',
  error: null
}

const details: SoftwarePackageDetails = { package: packageInfo, current_action: null, result: null }
const translate = (key: string) => key

function client(overrides: Partial<SoftwareClient> = {}): SoftwareClient {
  return {
    listPackages: vi.fn().mockResolvedValue([packageInfo]),
    listCommands: vi.fn().mockResolvedValue([]),
    getPackage: vi.fn().mockResolvedValue(details),
    requestInstall: vi.fn().mockResolvedValue(pending),
    requestUninstall: vi.fn().mockResolvedValue({ ...pending, plan: { ...pending.plan, action: 'uninstall' } }),
    prepare: vi.fn().mockResolvedValue({ package: packageInfo, user_action: null, ui_kind: null, ui_target: null }),
    ...overrides
  }
}

describe('SoftwarePanel', () => {
  it('reads current installed state after a restart expires the old confirmation', async () => {
    const getPackage = vi.fn().mockRejectedValueOnce(new ApiClientError('Expired', 'service', 409, 'SOFTWARE_ACTION_EXPIRED'))
      .mockResolvedValue({ ...details, package: { ...packageInfo, installed_version: '1.4.4', availability: 'ready', reason: null } })
    const apiClient = client({ getPackage })
    const confirmSoftware = vi.fn()
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate, operationId: pending.operation_id } })
    await flushPromises()
    expect(getPackage).toHaveBeenNthCalledWith(2, 'siril')
    expect(wrapper.find('[data-testid="request-uninstall"]').exists()).toBe(true)
    expect(confirmSoftware).not.toHaveBeenCalled()
    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('offers bundle migration without uninstalling the existing standalone program', async () => {
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, package: {
      ...packageInfo, installed_version: '1.4.4', install_path: 'C:/workspace/software/siril/app', migration_required: true
    } }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    await wrapper.get('[data-testid="request-install"]').trigger('click')
    await flushPromises()
    expect(apiClient.requestUninstall).not.toHaveBeenCalled()
    expect(apiClient.requestInstall).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
  it('requests an install plan but waits for the separate confirmation action', async () => {
    const apiClient = client()
    const confirmSoftware = vi.fn()
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate } })
    await flushPromises()

    await wrapper.get('[data-testid="request-install"]').trigger('click')
    await flushPromises()

    expect(apiClient.requestInstall).toHaveBeenCalledWith('siril', {
      version: '1.4.4',
      package_token: 'package-token'
    })
    expect(confirmSoftware).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="confirm-software"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('confirms only after the plan is displayed and routes an install query to no side effect', async () => {
    const apiClient = client({
      getPackage: vi.fn().mockResolvedValue({ ...details, current_action: pending })
    })
    const confirmSoftware = vi.fn().mockResolvedValue({
      ok: true,
      pending: { ...pending, state: 'running' }
    })
    const wrapper = mount(SoftwarePanel, {
      props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate, packageId: 'siril', operationId: pending.operation_id }
    })
    await flushPromises()

    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    expect(confirmSoftware).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="software-plan"]').exists()).toBe(true)
    await wrapper.get('[data-testid="confirm-software"]').trigger('click')
    await flushPromises()
    expect(confirmSoftware).toHaveBeenCalledWith(pending.operation_id)
    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps confirmation disabled until the native page feature is available', async () => {
    const apiClient = client({
      getPackage: vi.fn().mockResolvedValue({ ...details, current_action: pending })
    })
    const wrapper = mount(SoftwarePanel, {
      props: {
        client: apiClient,
        confirmSoftware: vi.fn(),
        confirmationAvailable: false,
        translate,
        packageId: 'siril',
        operationId: pending.operation_id
      }
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="confirm-software"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})


describe('Compact package controls', () => {
  it.each(['not_installed', 'ready', 'not_ready', 'unknown'] as const)('shows only the mutation button and status for %s', async availability => {
    const installed = availability !== 'not_installed'
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, package: { ...packageInfo, availability, installed_version: installed ? '1.4.4' : null } }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.findAll('button')).toHaveLength(1)
    expect(wrapper.get('[data-testid="software-status"]').classes()).toContain(availability === 'ready' ? 'bg-success-background' : 'bg-error')
    expect(wrapper.find('select').exists()).toBe(false)
    expect(apiClient.listCommands).not.toHaveBeenCalled()
    expect(apiClient.prepare).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('cancels uninstall confirmation without deleting or confirming', async () => {
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, package: { ...packageInfo, availability: 'ready', installed_version: '1.4.4' } }) })
    const confirmSoftware = vi.fn()
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate } })
    await flushPromises()
    await wrapper.get('[data-testid="request-uninstall"]').trigger('click')
    await flushPromises()
    expect(apiClient.requestUninstall).toHaveBeenCalledWith('siril', { package_token: 'package-token' })
    expect(wrapper.text()).toContain('apfSoftware.uninstallNotice')
    await wrapper.findAll('button').find(button => button.text() === 'apfSoftware.cancel')!.trigger('click')
    expect(wrapper.find('[data-testid="software-plan"]').exists()).toBe(false)
    expect(confirmSoftware).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows request failure without confirming and permits another attempt', async () => {
    const apiClient = client({ requestInstall: vi.fn().mockRejectedValue(new Error('network failed')) })
    const confirmSoftware = vi.fn()
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate } })
    await flushPromises()
    await wrapper.get('[data-testid="request-install"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('network failed')
    expect(confirmSoftware).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="request-install"]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })
})


it('allows removal of a known failed partial program without claiming a version is installed', async () => {
  const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, package: {
    ...packageInfo, availability: 'not_ready', installed_version: null, install_path: 'C:/workspace/software/siril/app', operation_state: 'failed', reason: 'Installation incomplete'
  } }) })
  const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
  await flushPromises()
  expect(wrapper.get('[data-testid="software-status"]').classes()).toContain('bg-error')
  await wrapper.get('[data-testid="request-uninstall"]').trigger('click')
  await flushPromises()
  expect(apiClient.requestUninstall).toHaveBeenCalledWith('siril', { package_token: 'package-token' })
  expect(apiClient.requestInstall).not.toHaveBeenCalled()
  wrapper.unmount()
})
