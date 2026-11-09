<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { projectLinks } from '../projectLinks'
import SystemStatsPanel from '@/components/common/SystemStatsPanel.vue'
import { useSystemStatsStore } from '@/stores/systemStatsStore'
import upstreamLicense from '../../../../LICENSE?url'
const { t } = useI18n()
const statsStore = useSystemStatsStore()
const version = __ASTROPHOTOFLOW_VERSION__
const frontendVersion = __COMFYUI_FRONTEND_VERSION__
</script>

<template>
  <section class="flex min-w-0 flex-col gap-5" data-testid="apf-about-panel">
    <header>
      <h2 class="mb-2 text-2xl font-semibold">AstroPhotoFlow</h2>
      <p class="text-sm text-muted-foreground">
        {{ t('apfSettings.description') }}
      </p>
      <p class="text-sm">{{ t('apfSettings.version') }} {{ version }}</p>
    </header>
    <nav class="flex flex-wrap gap-4 text-sm">
      <a
        class="underline"
        :href="projectLinks.documentation"
        target="_blank"
        rel="noopener noreferrer"
        >{{ t('apfSettings.documentation') }}</a
      >
      <a
        class="underline"
        :href="projectLinks.feedback"
        target="_blank"
        rel="noopener noreferrer"
        >{{ t('apfSettings.feedback') }}</a
      >
      <a
        class="underline"
        :href="projectLinks.license"
        target="_blank"
        rel="noopener noreferrer"
        >{{ t('apfSettings.license') }}</a
      >
    </nav>
    <details class="border-t border-border-default pt-4">
      <summary class="cursor-pointer font-medium">
        {{ t('apfSettings.components') }}
      </summary>
      <div class="mt-4 space-y-3 text-sm">
        <p>
          <a
            class="underline"
            href="https://github.com/Comfy-Org/ComfyUI"
            target="_blank"
            rel="noopener noreferrer"
            >ComfyUI</a
          >
          {{ statsStore.systemStats?.system.comfyui_version }}
        </p>
        <p>
          <a
            class="underline"
            href="https://github.com/Comfy-Org/ComfyUI_frontend"
            target="_blank"
            rel="noopener noreferrer"
            >ComfyUI_frontend</a
          >
          {{ frontendVersion }}
        </p>
        <p>{{ t('apfSettings.componentsHelp') }}</p>
        <a
          class="underline"
          :href="upstreamLicense"
          target="_blank"
          rel="noopener noreferrer"
          >{{ t('apfSettings.license') }} (GPLv3)</a
        >
      </div>
    </details>
    <details
      v-if="statsStore.systemStats"
      class="min-w-0 border-t border-border-default pt-4"
    >
      <summary class="cursor-pointer font-medium">
        {{ t('apfSettings.diagnostics') }}
      </summary>
      <div class="mt-4 min-w-0">
        <SystemStatsPanel :stats="statsStore.systemStats" />
      </div>
    </details>
  </section>
</template>
