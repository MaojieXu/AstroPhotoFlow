import { defineAsyncComponent } from 'vue'

import { isCloud, isDesktop } from '@/platform/distribution/types'

export default isCloud
  ? window.__CONFIG__?.subscription_required
    ? defineAsyncComponent(() => import('./CloudRunButtonWrapper.vue'))
    : defineAsyncComponent(() => import('./ComfyQueueButton.vue'))
  : isDesktop
    ? defineAsyncComponent(() => import('./LocalRunButtonWrapper.vue'))
    : defineAsyncComponent(() => import('./ComfyQueueButton.vue'))
