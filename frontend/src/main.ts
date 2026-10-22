import { createApp, type App as VueApp } from 'vue'
import { app } from '../../scripts/app.js'

import SidebarContent from './App.vue'
import './styles.css'

const stylesheet = document.createElement('link')
stylesheet.rel = 'stylesheet'
const stylesheetUrl = new URL(import.meta.url)
stylesheetUrl.pathname = stylesheetUrl.pathname.replace(/[^/]+$/, 'astrophotoflow.css')
stylesheet.href = stylesheetUrl.href

app.registerExtension({
  name: 'astrophotoflow.sidebar',
  async setup() {
    await new Promise<void>((resolve, reject) => {
      stylesheet.onload = () => resolve()
      stylesheet.onerror = () => reject(new Error('AstroPhotoFlow stylesheet failed to load'))
      document.head.append(stylesheet)
    })

    let sidebarApp: VueApp | undefined

    app.extensionManager.registerSidebarTab({
      id: 'astrophotoflow',
      title: '天文',
      tooltip: 'AstroPhotoFlow',
      icon: 'pi pi-star',
      type: 'custom',
      render(container) {
        sidebarApp?.unmount()
        sidebarApp = createApp(SidebarContent)
        sidebarApp.mount(container)
      },
      destroy() {
        sidebarApp?.unmount()
        sidebarApp = undefined
      }
    })
  }
})
