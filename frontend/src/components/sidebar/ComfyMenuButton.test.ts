import userEvent from '@testing-library/user-event'
import { render, screen } from '@testing-library/vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import { createI18n } from 'vue-i18n'

import { useSettingStore } from '@/platform/settings/settingStore'
import { useSettingsDialog } from '@/platform/settings/composables/useSettingsDialog'
import { useMenuItemStore } from '@/stores/menuItemStore'

import ComfyMenuButton from './ComfyMenuButton.vue'

vi.mock(import('@/platform/telemetry'))
vi.mock(import('@/platform/settings/composables/useSettingsDialog'))
vi.mock(import('@/platform/distribution/types'), () => ({
  get DISTRIBUTION() {
    return __DISTRIBUTION__
  },
  get isCloud() {
    return __DISTRIBUTION__ === 'cloud'
  },
  get isDesktop() {
    return __DISTRIBUTION__ === 'desktop'
  },
  isNightly: false
}))

const NODES_2_LABEL = 'Nodes 2.0'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      g: { beta: 'BETA', settings: 'Settings' },
      menu: { theme: 'Theme', manageExtensions: 'Manage Extensions' },
      menuLabels: { 'Browse Templates': 'Browse Templates', Help: 'Help' }
    }
  }
})

async function openMenu({ vueNodesEnabled = false } = {}) {
  const user = userEvent.setup()
  const enabled = ref(vueNodesEnabled)
  const settingStore = useSettingStore()

  vi.mocked(settingStore.get).mockImplementation((key) =>
    key === 'Comfy.VueNodes.Enabled' ? enabled.value : undefined
  )
  vi.mocked(settingStore.set).mockImplementation(async (key, value) => {
    if (key === 'Comfy.VueNodes.Enabled') enabled.value = Boolean(value)
  })

  render(ComfyMenuButton, {
    global: {
      plugins: [i18n],
      directives: { tooltip: () => {} }
    }
  })

  await user.click(screen.getByTestId('comfy-menu-button'))

  return {
    user,
    settingStore
  }
}

describe('ComfyMenuButton', () => {
  beforeEach(() => {
    vi.stubGlobal('__DISTRIBUTION__', 'desktop')
  })

  it('keeps settings accessible while hiding the local-only menu exclusions', async () => {
    vi.stubGlobal('__DISTRIBUTION__', 'localhost')
    useMenuItemStore().menuItems = [
      {
        key: 'Help',
        label: 'Help',
        items: [{ label: 'Documentation', command: vi.fn() }]
      }
    ]
    const show = vi.fn()
    vi.mocked(useSettingsDialog).mockReturnValue({
      show,
      hide: vi.fn(),
      showAbout: vi.fn()
    })

    const menu = await openMenu()

    for (const label of [
      NODES_2_LABEL,
      'Browse Templates',
      'Manage Extensions',
      'Help'
    ]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument()
    }
    await menu.user.click(screen.getByRole('menuitem', { name: 'Settings' }))
    expect(show).toHaveBeenCalledExactlyOnceWith(undefined)
  })

  describe.for(['row', 'label'] as const)('clicking the %s', (target) => {
    it('toggles Nodes 2.0 exactly once', async () => {
      const menu = await openMenu()

      await menu.user.click(
        target === 'row'
          ? screen.getByRole('menuitemcheckbox', { name: NODES_2_LABEL })
          : screen.getByText(NODES_2_LABEL)
      )

      expect(menu.settingStore.set).toHaveBeenCalledExactlyOnceWith(
        'Comfy.VueNodes.Enabled',
        true
      )
    })
  })

  describe.for([
    { enabled: false, written: true },
    { enabled: true, written: false }
  ])('while Nodes 2.0 is $enabled', ({ enabled, written }) => {
    it('writes the opposite value and shows it on the switch', async () => {
      const menu = await openMenu({ vueNodesEnabled: enabled })

      await menu.user.click(
        screen.getByRole('menuitemcheckbox', { name: NODES_2_LABEL })
      )

      expect(menu.settingStore.set).toHaveBeenCalledExactlyOnceWith(
        'Comfy.VueNodes.Enabled',
        written
      )
      await nextTick()
      expect(
        screen.getByRole('menuitemcheckbox', { name: NODES_2_LABEL })
      ).toHaveAttribute('aria-checked', String(written))
    })
  })

  it('does not advertise Nodes 2.0 as beta', async () => {
    await openMenu()

    expect(screen.queryByText('BETA')).not.toBeInTheDocument()
  })
})
