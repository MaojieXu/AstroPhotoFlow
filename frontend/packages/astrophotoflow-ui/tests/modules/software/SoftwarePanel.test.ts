import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

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
const release = { bundle_version: '0.2.0-dev.1', software_version: '1.4.4', channel: 'dev' as const,
  tag: 'v0.2.0-dev.1', commit: 'a'.repeat(40), is_latest: true, compatible: true,
  reason_code: null, reason_parameters: {}, release_token: 'release-token' }
const releaseList = { package_id: 'siril', releases: [release], checked_at: '2026-10-30T23:00:00Z', stale: false, error: null }
const releaseValue = release.tag + '@' + release.commit

function client(overrides: Partial<SoftwareClient> = {}): SoftwareClient {
  return {
    listReleases: vi.fn().mockResolvedValue(releaseList),
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
  it('shows every maintained package in its own row', async () => {
    const other = { ...packageInfo, package_id: 'other', name: 'Other Bundle' }
    const apiClient = client({ listPackages: vi.fn().mockResolvedValue([packageInfo, other]),
      getPackage: vi.fn().mockImplementation(id => Promise.resolve({ ...details, package: id === 'siril' ? packageInfo : other })) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.findAll('[data-testid="software-package-row"]')).toHaveLength(2)
    expect(apiClient.listReleases).toHaveBeenCalledWith('siril')
    expect(apiClient.listReleases).toHaveBeenCalledWith('other')
    wrapper.unmount()
  })

  it('prefers a compatible stable release and disables an incompatible latest', async () => {
    const incompatible = { ...release, bundle_version: '2.0.0', channel: 'stable' as const, tag: 'v2.0.0', commit: 'b'.repeat(40), compatible: false, reason_code: 'unsupported_sdk' as const, reason_parameters: { required: '3' }, release_token: null }
    const stable = { ...release, bundle_version: '1.0.0', channel: 'stable' as const, tag: 'v1.0.0', commit: 'c'.repeat(40), is_latest: false }
    const apiClient = client({ listReleases: vi.fn().mockResolvedValue({ ...releaseList, releases: [incompatible, release, stable] }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.get('select').element.value).toBe(stable.tag + '@' + stable.commit)
    expect(wrapper.findAll('option').find(option => option.attributes('value') === incompatible.tag + '@' + incompatible.commit)?.attributes('disabled')).toBeDefined()
    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('retains the selected version during language changes and version refresh', async () => {
    const language = ref('en')
    const older = { ...release, tag: 'v0.1.2-dev.1', bundle_version: '0.1.2-dev.1', commit: 'b'.repeat(40), is_latest: false }
    const newer = { ...release, tag: 'v0.3.0-dev.1', bundle_version: '0.3.0-dev.1', commit: 'c'.repeat(40) }
    const apiClient = client({ listReleases: vi.fn().mockResolvedValueOnce({ ...releaseList, releases: [release, older] })
      .mockResolvedValueOnce({ ...releaseList, releases: [newer, release, older] }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate: key => language.value + ':' + key } })
    await flushPromises()
    const chosen = older.tag + '@' + older.commit
    await wrapper.get('select').setValue(chosen)
    language.value = 'zh'
    await flushPromises()
    expect(wrapper.get('select').element.value).toBe(chosen)
    expect(apiClient.listReleases).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('zh:apfSoftware.channel.dev')
    await wrapper.get('[data-testid="refresh-versions"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('select').element.value).toBe(chosen)
    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('retains installed controls when version discovery fails', async () => {
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, package: { ...packageInfo, installed_version: '1.4.4', bundle_version: '0.1.2-dev.1', bundle_commit: 'b'.repeat(40), availability: 'ready' } }),
      listReleases: vi.fn().mockResolvedValue({ ...releaseList, stale: true, error: { code: 'RELEASE_CHECK_FAILED', message: 'Network', fields: [] } }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.get('select').element.value).toBe('__installed__')
    expect(wrapper.get('[data-testid="request-uninstall"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('apfSoftware.releaseCheckFailed')
    wrapper.unmount()
  })

  it('creates a new plan when selection differs from the pending target', async () => {
    const oldPlan = { ...pending, plan: { ...pending.plan, target_bundle_version: '0.1.2-dev.1', target_commit: 'b'.repeat(40) } }
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, current_action: oldPlan }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    await wrapper.get('[data-testid="software-plan"]').trigger('close')
    await wrapper.get('[data-testid="request-install"]').trigger('click')
    await flushPromises()
    expect(apiClient.requestInstall).toHaveBeenCalledWith('siril', { version: '1.4.4', package_token: 'package-token', bundle_version: release.bundle_version, release_token: release.release_token })
    wrapper.unmount()
  })

  it('keeps an unsaved final result visible after reload without showing ready or reinstalling', async () => {
    const error = { code: 'SOFTWARE_STATE_SAVE_FAILED', message: '安装结果未能保存，需核对软件状态；请勿直接重复安装。', fields: [] }
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details,
      package: { ...packageInfo, installed_version: '1.4.4', availability: 'ready' },
      current_action: { ...pending, state: 'failed', error }
    }) })
    const confirmSoftware = vi.fn()
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain(error.message)
    expect(wrapper.get('[data-testid="software-status"]').classes()).not.toContain('bg-success-background')
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain(error.message)
    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    expect(confirmSoftware).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows the reported percentage and its actual installation phase', async () => {
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details,
      package: { ...packageInfo, phase: 'downloading', progress: 0.42 },
      current_action: { ...pending, state: 'running' }
    }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.text()).toContain('42%')
    expect(wrapper.text()).toContain('apfSoftware.installPhase.downloading')
    expect(wrapper.get('[aria-label="apfSoftware.installPhase.downloading"]').attributes('value')).toBe('0.42')
    wrapper.unmount()
  })

  it('shows indeterminate installation progress and hides it after completion', async () => {
    vi.useFakeTimers()
    const getPackage = vi.fn()
      .mockResolvedValueOnce({ ...details, current_action: { ...pending, state: 'running' } })
      .mockResolvedValue({ ...details, current_action: { ...pending, state: 'completed' } })
    const wrapper = mount(SoftwarePanel, { props: {
      client: client({ getPackage }), confirmSoftware: vi.fn(), confirmationAvailable: true, translate
    } })
    try {
      await flushPromises()
      expect(wrapper.get('[aria-label="apfSoftware.installing"]').attributes('value')).toBeUndefined()
      await vi.advanceTimersByTimeAsync(1000)
      await flushPromises()
      expect(wrapper.find('[aria-label="apfSoftware.installing"]').exists()).toBe(false)
    } finally {
      wrapper.unmount()
      vi.useRealTimers()
    }
  })

  it('reviews an available bundle update before confirming it', async () => {
    const update = { ...pending, plan: { ...pending.plan, action: 'update' as const } }
    const apiClient = client({
      getPackage: vi.fn().mockResolvedValue({ ...details, package: { ...packageInfo,
        installed_version: '1.4.4', availability: 'ready', update_available: true } }),
      requestInstall: vi.fn().mockResolvedValue(update)
    })
    const confirmSoftware = vi.fn().mockResolvedValue({ ok: true, pending: { ...update, state: 'completed' } })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware, confirmationAvailable: true, translate } })
    await flushPromises()
    await wrapper.get('select[aria-label="apfSoftware.bundleVersion"]').setValue(releaseValue)
    await wrapper.get('[data-testid="request-update"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="confirm-software"]').text()).toBe('apfSoftware.switchVersion')
    expect(confirmSoftware).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="confirm-software"]').trigger('click')
    await flushPromises()
    expect(confirmSoftware).toHaveBeenCalledWith(pending.operation_id)
    wrapper.unmount()
  })
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
      package_token: 'package-token', bundle_version: release.bundle_version, release_token: release.release_token
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
  it.each(['not_installed', 'ready', 'not_ready', 'unknown'] as const)('shows version selection and explicit actions for %s', async availability => {
    const installed = availability !== 'not_installed'
    const apiClient = client({ getPackage: vi.fn().mockResolvedValue({ ...details, package: { ...packageInfo, availability, installed_version: installed ? '1.4.4' : null } }) })
    const wrapper = mount(SoftwarePanel, { props: { client: apiClient, confirmSoftware: vi.fn(), confirmationAvailable: true, translate } })
    await flushPromises()
    expect(wrapper.findAll('select')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="refresh-versions"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="request-install"]').exists()).toBe(!installed)
    expect(wrapper.find('[data-testid="request-update"]').exists()).toBe(installed)
    expect(wrapper.find('[data-testid="request-uninstall"]').exists()).toBe(installed)
    expect(apiClient.requestInstall).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="software-status"]').classes()).toContain(availability === 'ready' ? 'bg-success-background' : 'bg-error')
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
