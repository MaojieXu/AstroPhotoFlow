import { createRouter, createWebHashHistory } from 'vue-router'

import { useUserStore } from '@/stores/userStore'
import NativeShell from '@/views/NativeShell.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/workflows' },
    {
      path: '/workflows',
      component: NativeShell,
      beforeEnter: async () => {
        await useUserStore().initialize()
      }
    },
    { path: '/:pathMatch(.*)*', redirect: '/workflows' }
  ]
})
