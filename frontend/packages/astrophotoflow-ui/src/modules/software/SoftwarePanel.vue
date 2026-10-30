<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Component } from 'vue'
import { ApiClientError } from '../../core/client'

import type { SoftwareClient } from './api/client'
import type { PendingSoftwareAction, SoftwareConfirmationResult, SoftwarePackageDetails } from './api/contracts'

const props = defineProps<{
  client: SoftwareClient
  confirmSoftware: (operationId: string) => Promise<SoftwareConfirmationResult>
  confirmationAvailable: boolean
  translate: (key: string) => string
  controls?: { button: Component; dialog: Component }
  packageId?: string
  operationId?: string
}>()

type PanelState =
  | { phase: 'loading' }
  | { phase: 'ready' | 'requesting' | 'confirming'; details: SoftwarePackageDetails; error: string | null }
  | { phase: 'error'; error: string }

const state = ref<PanelState>({ phase: 'loading' })
const planOpen = ref(false)
const details = computed(() => 'details' in state.value ? state.value.details : null)
const software = computed(() => details.value?.package)
const action = computed(() => details.value?.current_action)
const busy = computed(() => state.value.phase === 'requesting' || state.value.phase === 'confirming' || action.value?.state === 'running')
const installed = computed(() => !software.value?.migration_required && (software.value?.installed_version != null || software.value?.install_path != null))
const uninstallAction = computed(() => action.value?.state === 'running' ? action.value.plan.action === 'uninstall' : installed.value)
const stateSaveFailed = computed(() => action.value?.error?.code === 'SOFTWARE_STATE_SAVE_FAILED' || software.value?.last_error?.code === 'SOFTWARE_STATE_SAVE_FAILED')
const ready = computed(() => software.value?.availability === 'ready' && !busy.value && !stateSaveFailed.value)
const progressLabel = computed(() => props.translate(software.value?.phase ? 'apfSoftware.installPhase.' + software.value.phase : 'apfSoftware.installing'))
const statusText = computed(() => {
  if (busy.value) return props.translate(action.value?.plan.action === 'uninstall' ? 'apfSoftware.uninstalling' : 'apfSoftware.installing')
  const actionError = action.value?.error
  if (actionError?.code === 'SOFTWARE_STATE_SAVE_FAILED') return actionError.message
  return software.value?.last_error?.message ?? software.value?.reason ?? props.translate(`apfSoftware.availability.${software.value?.availability ?? 'unknown'}`)
})
let disposed = false
let generation = 0
let pollTimer: ReturnType<typeof setTimeout> | undefined

function message(cause: unknown) {
  return cause instanceof Error ? cause.message : props.translate('apfSoftware.loadError')
}

function schedulePoll(pending: PendingSoftwareAction) {
  clearTimeout(pollTimer)
  const current = generation
  pollTimer = setTimeout(async () => {
    try {
      const result = await props.client.getPackage(pending.plan.package_id, pending.operation_id)
      if (disposed || current !== generation) return
      state.value = { phase: 'ready', details: result, error: result.current_action?.error?.message ?? null }
      if (result.current_action?.state === 'running') schedulePoll(result.current_action)
    } catch (cause) {
      if (disposed || current !== generation || !details.value) return
      state.value = { phase: 'ready', details: details.value, error: message(cause) }
    }
  }, 1000)
}

async function load() {
  clearTimeout(pollTimer)
  const current = ++generation
  state.value = { phase: 'loading' }
  try {
    const packages = await props.client.listPackages()
    const id = props.packageId ?? packages[0]?.package_id
    if (!id) throw new Error(props.translate('apfSoftware.noPackages'))
    let result: SoftwarePackageDetails
    try {
      result = await props.client.getPackage(id, props.operationId)
    } catch (cause) {
      if (!(cause instanceof ApiClientError) || cause.code !== 'SOFTWARE_ACTION_EXPIRED') throw cause
      result = await props.client.getPackage(id)
    }
    if (disposed || current !== generation) return
    state.value = { phase: 'ready', details: result, error: result.current_action?.error?.message ?? result.package.last_error?.message ?? null }
    planOpen.value = result.current_action?.state === 'awaiting_confirmation'
    if (result.current_action?.state === 'running') schedulePoll(result.current_action)
  } catch (cause) {
    if (!disposed && current === generation) state.value = { phase: 'error', error: message(cause) }
  }
}

async function requestAction(kind: 'install' | 'update' | 'uninstall') {
  const current = details.value
  if (!current || busy.value) return
  if (action.value?.state === 'awaiting_confirmation') {
    planOpen.value = true
    return
  }
  state.value = { phase: 'requesting', details: current, error: null }
  try {
    const result = kind === 'uninstall'
      ? await props.client.requestUninstall(current.package.package_id, { package_token: current.package.package_token })
      : await props.client.requestInstall(current.package.package_id, {
          version: current.package.available_versions[0], package_token: current.package.package_token
        })
    if (disposed) return
    state.value = { phase: 'ready', details: { ...current, current_action: result, result: null }, error: null }
    planOpen.value = true
  } catch (cause) {
    if (!disposed) state.value = { phase: 'ready', details: current, error: message(cause) }
  }
}

async function confirmAction() {
  const current = details.value
  const pending = action.value
  if (!current || !pending || pending.state !== 'awaiting_confirmation' || busy.value || !props.confirmationAvailable) return
  state.value = { phase: 'confirming', details: current, error: null }
  try {
    const result = await props.confirmSoftware(pending.operation_id)
    if (disposed) return
    if (!result.ok) {
      state.value = { phase: 'ready', details: current, error: result.message ?? props.translate('apfSoftware.confirmationFailed') }
      return
    }
    state.value = { phase: 'ready', details: { ...current, current_action: result.pending }, error: null }
    planOpen.value = false
    if (result.pending.state === 'running') schedulePoll(result.pending)
  } catch (cause) {
    if (!disposed) state.value = { phase: 'ready', details: current, error: message(cause) }
  }
}

onMounted(() => void load())
watch(() => [props.packageId, props.operationId], () => void load())
onBeforeUnmount(() => {
  disposed = true
  generation++
  clearTimeout(pollTimer)
})
</script>

<template>
  <section class="flex flex-col gap-2 p-3" data-testid="software-panel">
    <div v-if="state.phase === 'loading'" role="status" class="text-sm text-muted-foreground">{{ translate('apfSoftware.loading') }}</div>
    <template v-else>
      <div v-if="software" class="flex min-h-12 items-center gap-3 rounded-md px-2 text-sm hover:bg-interface-menu-component-surface-hovered">
        <span
          data-testid="software-status"
          class="size-2 shrink-0 rounded-full focus-visible:outline-2 focus-visible:outline-offset-2"
          :class="ready ? 'bg-success-background' : 'bg-error'"
          :title="statusText"
          :aria-label="statusText"
          role="img"
          tabindex="0"
        />
        <span class="min-w-0 flex-1 truncate font-medium">{{ software.name }}</span>
        <component
          :is="controls?.button ?? 'button'" v-if="software.update_available"
          type="button" size="sm" variant="primary" class="h-8 shrink-0"
          :disabled="busy || software.operation_state === 'unknown'"
          data-testid="request-update" @click="requestAction('update')"
        >{{ translate('apfSoftware.update') }}</component>
        <component
          :is="controls?.button ?? 'button'"
          type="button" size="sm" :variant="uninstallAction ? 'secondary' : 'primary'"
          class="h-8 shrink-0" :disabled="busy || software.operation_state === 'unknown'"
          :loading="busy" :data-testid="uninstallAction ? 'request-uninstall' : 'request-install'" @click="requestAction(uninstallAction ? 'uninstall' : 'install')"
        >{{ translate(uninstallAction ? 'apfSoftware.uninstall' : 'apfSoftware.install') }}</component>
      </div>
      <div
        v-if="action?.state === 'running' && action.plan.action !== 'uninstall'"
        class="flex flex-col gap-1 px-2"
      >
        <div class="flex justify-between text-xs text-muted-foreground">
          <span>{{ progressLabel }}</span>
          <span v-if="software?.progress != null">{{ Math.round(software.progress * 100) }}%</span>
        </div>
        <progress class="block h-1 w-full" :value="software?.progress ?? undefined" :max="1" :aria-label="progressLabel" />
      </div>
      <div v-if="'error' in state && state.error" role="alert" class="px-2 text-sm text-error">
        {{ state.error }}
        <component :is="controls?.button ?? 'button'" type="button" size="sm" variant="textonly" @click="load">{{ translate('apfSoftware.reload') }}</component>
      </div>
    </template>
    <component
      :is="controls?.dialog ?? 'div'"
      v-if="planOpen && action"
      :open="planOpen" :busy="state.phase === 'confirming'" role="dialog"
      :title="translate(action.plan.action === 'uninstall' ? 'apfSoftware.confirmUninstall' : action.plan.action === 'update' ? 'apfSoftware.confirmUpdate' : 'apfSoftware.confirmInstall')"
      data-testid="software-plan" @close="planOpen = false"
    >
      <div class="flex min-h-0 flex-col gap-3 overflow-y-auto p-4 text-sm">
        <div class="font-medium">{{ software?.name }} {{ action.plan.target_version ?? action.plan.current_version }}</div>
        <p v-if="action.plan.restart_required">{{ action.plan.restart_reason }}</p>
          <p v-if="action.plan.action === 'uninstall'">{{ translate('apfSoftware.uninstallNotice') }}</p>
        <template v-else>
          <a v-if="action.plan.source" :href="action.plan.source.split(' @ ')[0]" target="_blank" rel="noreferrer" class="break-all underline">{{ action.plan.source }}</a>
          <p class="break-all">{{ action.plan.install_path }}</p>
          <p v-for="node in action.plan.node_changes" :key="node.definition_id">{{ node.name }}</p>
        </template>
        <p v-if="!confirmationAvailable" role="status">{{ translate('apfSoftware.confirmationUnavailable') }}</p>
        <p v-if="'error' in state && state.error" role="alert" class="text-error">{{ state.error }}</p>
      </div>
      <div class="flex shrink-0 justify-end gap-2 border-t border-interface-stroke p-3">
        <component :is="controls?.button ?? 'button'" type="button" size="sm" variant="secondary" :disabled="state.phase === 'confirming'" @click="planOpen = false">{{ translate('apfSoftware.cancel') }}</component>
        <component :is="controls?.button ?? 'button'" type="button" size="sm" variant="primary" :disabled="busy || !confirmationAvailable" data-testid="confirm-software" @click="confirmAction">{{ translate(action.plan.action === 'uninstall' ? 'apfSoftware.uninstall' : action.plan.action === 'update' ? 'apfSoftware.update' : 'apfSoftware.install') }}</component>
      </div>
    </component>
  </section>
</template>
