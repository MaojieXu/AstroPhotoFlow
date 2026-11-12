<template>
  <WorkspaceAuthGate>
    <main class="relative size-full overflow-hidden">
      <router-view />
    </main>
  </WorkspaceAuthGate>
</template>

<script setup lang="ts">
import { useFavicon } from '@vueuse/core'

import astroPhotoFlowMark from '@/assets/astrophotoflow.svg?no-inline'
import { isCloud, isDesktop } from '@/platform/distribution/types'
import WorkspaceAuthGate from '@/platform/workspace/auth/WorkspaceAuthGate.vue'

useFavicon(isCloud || isDesktop ? '/assets/favicon.ico' : astroPhotoFlowMark)
</script>
