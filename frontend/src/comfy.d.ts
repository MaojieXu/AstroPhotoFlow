declare module '*scripts/app.js' {
  interface SidebarTab {
    id: string
    title: string
    tooltip: string
    icon: string
    type: 'custom'
    render: (container: HTMLElement) => void
    destroy: () => void
  }

  interface ComfyExtension {
    name: string
    setup: () => Promise<void>
  }

  export const app: {
    extensionManager: {
      registerSidebarTab: (tab: SidebarTab) => void
    }
    registerExtension: (extension: ComfyExtension) => void
  }
}
