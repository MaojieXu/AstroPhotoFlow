import { describe, expect, it, vi } from 'vitest'

import { useCommandStore } from '@/stores/commandStore'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

vi.mock(import('@/i18n'), () => ({
  t: (key: string) => key,
  te: () => false
}))

describe('useSidebarTabStore', () => {
  const registerTab = (onToggle?: () => Promise<boolean>) => {
    const store = useSidebarTabStore()
    store.registerSidebarTab({
      id: 'tab',
      title: 'tab',
      type: 'vue',
      component: {},
      onToggle
    })
    return store
  }

  const runToggleCommand = async () => {
    const toggleCommand = useCommandStore().commands.find(
      (command) => command.id === 'Workspace.ToggleSidebarTab.tab'
    )
    await toggleCommand?.function()
  }

  describe('toggle command', () => {
    it('keeps the current panel when its draft prevents leaving', async () => {
      const store = registerTab()
      store.registerSidebarTab({
        id: 'library',
        title: 'library',
        type: 'vue',
        component: {},
        canClose: () => false
      })
      store.activeSidebarTabId = 'library'
      await runToggleCommand()
      expect(store.activeSidebarTabId).toBe('library')
      await store.closeSidebarTab()
      expect(store.activeSidebarTabId).toBe('library')
    })

    it('allows switching and closing after the current panel permits leaving', async () => {
      const store = registerTab()
      store.registerSidebarTab({
        id: 'library',
        title: 'library',
        type: 'vue',
        component: {},
        canClose: () => true
      })
      store.activeSidebarTabId = 'library'
      await runToggleCommand()
      expect(store.activeSidebarTabId).toBe('tab')
      await store.closeSidebarTab()
      expect(store.activeSidebarTabId).toBeNull()
    })

    it.for([
      { hook: 'none', onToggle: undefined, activeTabId: 'tab' },
      { hook: 'declines', onToggle: async () => false, activeTabId: 'tab' },
      { hook: 'handles', onToggle: async () => true, activeTabId: null }
    ])(
      'activates the tab unless the onToggle hook handles it ($hook)',
      async ({ onToggle, activeTabId }) => {
        const store = registerTab(onToggle)

        await runToggleCommand()

        expect(store.activeSidebarTabId).toBe(activeTabId)
      }
    )
  })
})
