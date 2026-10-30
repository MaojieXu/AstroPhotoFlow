<template>
  <div v-if="settingGroups.length > 0">
    <SettingGroup
      v-for="(group, i) in regularGroups"
      :key="group.label"
      :divider="i !== 0"
      :group="group"
    />
    <details
      v-if="advancedGroups.length"
      :open="expandAdvanced"
      class="mt-6 border-t border-border-default pt-4"
    >
      <summary class="cursor-pointer font-medium">
        {{ $t('apfSettings.advanced') }}
      </summary>
      <p class="text-sm text-muted-foreground">
        {{ $t('apfSettings.precisionHelp') }}
      </p>
      <SettingGroup
        v-for="group in advancedGroups"
        :key="group.label"
        :group="group"
      />
    </details>
  </div>
  <NoResultsPlaceholder
    v-else
    icon="pi pi-search"
    :title="$t('g.noResultsFound')"
    :message="$t('g.searchFailedMessage')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { isAdvancedSetting } from '@/platform/astrophotoflow/settingsPresentation'
import NoResultsPlaceholder from '@/components/common/NoResultsPlaceholder.vue'
import SettingGroup from '@/platform/settings/components/SettingGroup.vue'
import type { ISettingGroup } from '@/platform/settings/types'

const { settingGroups, expandAdvanced = false } = defineProps<{
  settingGroups: ISettingGroup[]
  expandAdvanced?: boolean
}>()
const regularGroups = computed(() =>
  settingGroups
    .map((group) => ({
      ...group,
      settings: group.settings.filter((setting) => !isAdvancedSetting(setting))
    }))
    .filter((group) => group.settings.length)
)
const advancedGroups = computed(() =>
  settingGroups
    .map((group) => ({
      ...group,
      settings: group.settings.filter(isAdvancedSetting)
    }))
    .filter((group) => group.settings.length)
)
</script>
