import { createRouter, createWebHashHistory } from 'vue-router'

import { useUserStore } from '@/stores/userStore'
import NativeShell from '@/views/NativeShell.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/library' },
    {
      path: '/:page(library|workflows|equipment)',
      component: NativeShell,
      props: true,
      beforeEnter: async () => {
        await useUserStore().initialize()
      }
    },
    { path: '/:pathMatch(.*)*', redirect: '/library' }
  ]
})
