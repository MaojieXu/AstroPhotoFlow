<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import type { Component } from 'vue'
import { useSoftwareDetails, useSoftwareReleases, type SoftwareDetailsRequest } from './queries'
import { useSoftwareActionRequest, useSoftwareConfirmation } from './mutations'

import type { SoftwareClient } from './api/client'
import type { PendingSoftwareAction, SoftwareConfirmationResult, SoftwarePackageDetails, SoftwareRelease } from './api/contracts'

const props = defineProps<{
  workspaceId: string
  client: SoftwareClient
  confirmSoftware: (operationId: string) => Promise<SoftwareConfirmationResult>
  confirmationAvailable: boolean
  translate: (key: string, values?: Record<string, unknown>) => string
  controls?: { button: Component; dialog: Component; select?: Component }
  packageId: string
  operationId?: string
}>()

type PanelState =
  | { phase: 'loading' }
  | { phase: 'ready' | 'requesting' | 'confirming'; details: SoftwarePackageDetails; error: string | null }
  | { phase: 'error'; error: string }

const intent = ref<'idle'|'requesting'|'confirming'|'reconciling'>('idle')
const actionFailure = ref<string|null>(null)
const actionSession = shallowRef({})
const operationId = ref(props.operationId)
const planOpen = ref(false)
function context(): SoftwareDetailsRequest {
  return {workspaceId:props.workspaceId,packageId:props.packageId,operationId:operationId.value,client:props.client}
}
const detailsQuery = useSoftwareDetails(context, () => intent.value==='requesting'||intent.value==='confirming')
const releasesQuery = useSoftwareReleases(context)
const requestMutation = useSoftwareActionRequest()
const confirmationMutation = useSoftwareConfirmation()
const details = computed(() => detailsQuery.data.value ?? null)
const state = computed<PanelState>(() => {
  if (!details.value) return detailsQuery.isError.value ? {phase:'error',error:message(detailsQuery.error.value)} : {phase:'loading'}
  const phase=intent.value==='requesting'||intent.value==='confirming'?intent.value:'ready'
  return {phase,details:details.value,error:actionFailure.value??details.value.current_action?.error?.message??details.value.package.last_error?.message??(detailsQuery.isError.value?message(detailsQuery.error.value):null)}
})
const software = computed(() => details.value?.package)
const action = computed(() => details.value?.current_action)
const busy = computed(() => intent.value!=='idle' || action.value?.state==='running')
const installed = computed(() => !software.value?.migration_required && (software.value?.installed_version != null || software.value?.install_path != null))
const uninstallAction = computed(() => action.value?.state === 'running' ? action.value.plan.action === 'uninstall' : installed.value)
const stateSaveFailed = computed(() => action.value?.error?.code === 'SOFTWARE_STATE_SAVE_FAILED' || software.value?.last_error?.code === 'SOFTWARE_STATE_SAVE_FAILED')
const ready = computed(() => (software.value?.development_source ? software.value.development_source.state === 'ready' : software.value?.availability === 'ready') && !busy.value && !stateSaveFailed.value)
const releases = releasesQuery.data
const releasesLoading = releasesQuery.isFetching
const releasesFailure = releasesQuery.isError
const selectedValue = ref('')
const rememberedSelection = shallowRef<SoftwareRelease>()
const releaseKey = (value: SoftwareRelease) => value.tag + '@' + value.commit
const isInstalledRelease = (value: SoftwareRelease) => value.bundle_version === software.value?.bundle_version && value.commit === software.value?.bundle_commit
const optionValue = (value: SoftwareRelease) => isInstalledRelease(value) ? '__installed__' : releaseKey(value)
const selectedRelease = computed(() => releases.value?.releases.find(value => optionValue(value) === selectedValue.value))
const canInstallSelection = computed(() => Boolean(selectedRelease.value?.compatible && selectedRelease.value.release_token && selectedRelease.value.software_version && !isInstalledRelease(selectedRelease.value)))
const versionOptions = computed(() => {
  const values = (releases.value?.releases ?? []).map(value => ({
    value: optionValue(value), disabled: !value.compatible, name: releaseLabel(value)
  }))
  if (installed.value && !values.some(value => value.value === '__installed__')) values.unshift({
    value: '__installed__', disabled: true,
    name: `${software.value?.bundle_version ?? props.translate('apfSoftware.versionUnknown')} · ${props.translate('apfSoftware.installed')}`
  })
  if (selectedValue.value && !values.some(value => value.value === selectedValue.value) && rememberedSelection.value) values.push({
    value: selectedValue.value, disabled: true,
    name: `${rememberedSelection.value.bundle_version} · ${props.translate('apfSoftware.versionUnavailable')}`
  })
  return values
})

function releaseLabel(value: SoftwareRelease) {
  const labels = [value.bundle_version, props.translate(`apfSoftware.channel.${value.channel}`)]
  if (value.is_latest) labels.push(props.translate(value.channel === 'stable' ? 'apfSoftware.latestStable' : 'apfSoftware.latestDev'))
  if (isInstalledRelease(value)) labels.push(props.translate('apfSoftware.installed'))
  if (value.reason_code) labels.push(props.translate(`apfSoftware.releaseReasons.${value.reason_code}`, value.reason_parameters))
  return labels.join(' · ')
}

function chooseDefault() {
  if (!software.value) return
  if (!installed.value && selectedValue.value === '__installed__') {
    selectedValue.value = ''
    rememberedSelection.value = undefined
  }
  if (rememberedSelection.value && isInstalledRelease(rememberedSelection.value)) selectedValue.value = '__installed__'
  if (selectedValue.value) return
  if (installed.value) selectedValue.value = '__installed__'
  else {
    const values = releases.value?.releases ?? []
    const preferred = values.find(value => value.compatible && value.channel === 'stable') ?? values.find(value => value.compatible)
    if (preferred) selectedValue.value = optionValue(preferred)
  }
}

watch(selectedRelease, value => { if (value) rememberedSelection.value = value })
watch([software, releases, action], chooseDefault)

function refreshReleases() { return releasesQuery.refetch({cancelRefetch:false}) }

function changeSelection(value: string | number | undefined) { selectedValue.value = String(value ?? '') }
function selectNative(event: Event) { if (event.target instanceof HTMLSelectElement) changeSelection(event.target.value) }
const progressLabel = computed(() => props.translate(software.value?.phase ? 'apfSoftware.installPhase.' + software.value.phase : 'apfSoftware.installing'))
const statusText = computed(() => {
  if (software.value?.development_source) return software.value.development_source.error ?? props.translate('apfSoftware.developmentReady')
  if (action.value?.state==='running') return props.translate(action.value?.plan.action === 'uninstall' ? 'apfSoftware.uninstalling' : 'apfSoftware.installing')
  const actionError = action.value?.error
  if (actionError?.code === 'SOFTWARE_STATE_SAVE_FAILED') return actionError.message
  return software.value?.last_error?.message ?? software.value?.reason ?? props.translate(`apfSoftware.availability.${software.value?.availability ?? 'unknown'}`)
})
function message(cause: unknown) {
  return cause instanceof Error ? cause.message : props.translate('apfSoftware.loadError')
}
function adopt(current: SoftwareDetailsRequest, result: SoftwarePackageDetails) {
  const nextOperation=result.current_action?.operation_id
  detailsQuery.adopt({...current,operationId:nextOperation},result)
  operationId.value=nextOperation
}
watch(detailsQuery.data, result => {
  if (result && result.current_action?.operation_id!==operationId.value) adopt(context(),result)
})
watch(() => [action.value?.operation_id,action.value?.state] as const, ([id,value],[oldId,oldValue]) => {
  if(value!=='awaiting_confirmation')planOpen.value=false
  else if(id!==oldId||oldValue!==value)planOpen.value=true
})
watch(() => [props.workspaceId,props.packageId,props.operationId,props.client] as const, () => {
  actionSession.value={}; operationId.value=props.operationId; intent.value='idle'; actionFailure.value=null
  planOpen.value=false; selectedValue.value=''; rememberedSelection.value=undefined
}, {flush:'sync'})
onBeforeUnmount(() => { actionSession.value={} })
async function load() {
  actionFailure.value=null
  const result=await detailsQuery.refetch({cancelRefetch:false})
  if(!result.isError)intent.value='idle'
}
async function reconcile(session: object) {
  if(session!==actionSession.value)return
  intent.value='reconciling'
  const result=await detailsQuery.refetch({cancelRefetch:false})
  if(session===actionSession.value&&!result.isError)intent.value='idle'
}
watch([detailsQuery.isFetching,detailsQuery.isError], ([fetching,error]) => {
  if(!fetching&&!error&&details.value&&intent.value==='reconciling')intent.value='idle'
})
async function requestAction(kind: 'install'|'update'|'uninstall') {
  const current=details.value
  if(!current||busy.value)return
  const selected=selectedRelease.value
  if(action.value?.state==='awaiting_confirmation' && (kind==='uninstall'?action.value.plan.action==='uninstall':
    action.value.plan.action!=='uninstall'&&action.value.plan.target_bundle_version===selected?.bundle_version&&action.value.plan.target_commit===selected?.commit)) {
    planOpen.value=true; return
  }
  if(kind!=='uninstall'&&(!canInstallSelection.value||!selected?.software_version||!selected.release_token))return
  const target=context(), session=actionSession.value
  intent.value='requesting'; actionFailure.value=null
  try {
    let result: PendingSoftwareAction
    if(kind==='uninstall') result=await requestMutation.mutateAsync({...target,kind,body:{package_token:current.package.package_token}})
    else {
      if(!selected?.software_version||!selected.release_token)throw new Error(props.translate('apfSoftware.selectVersion'))
      result=await requestMutation.mutateAsync({...target,kind:'install',body:{version:selected.software_version,package_token:current.package.package_token,bundle_version:selected.bundle_version,release_token:selected.release_token}})
    }
    if(session!==actionSession.value)return
    adopt(target,{...current,current_action:result,result:null})
    planOpen.value=true; intent.value='idle'
  } catch(cause) {
    if(session===actionSession.value){actionFailure.value=message(cause);await reconcile(session)}
  }
}
async function confirmAction() {
  const current=details.value, pending=action.value
  if(!current||!pending||pending.state!=='awaiting_confirmation'||busy.value||!props.confirmationAvailable)return
  const target=context(), session=actionSession.value
  intent.value='confirming'; actionFailure.value=null
  try {
    const result=await confirmationMutation.mutateAsync({...target,operationId:pending.operation_id,confirm:props.confirmSoftware})
    if(session!==actionSession.value)return
    if(!result.ok){actionFailure.value=result.message??props.translate('apfSoftware.confirmationFailed');await reconcile(session);return}
    adopt(target,{...current,current_action:result.pending})
    planOpen.value=false; intent.value='idle'
  } catch(cause) {
    if(session===actionSession.value){actionFailure.value=message(cause);await reconcile(session)}
  }
}
</script>

<template>
  <section class="flex flex-col gap-2 p-3" data-testid="software-package-row">
    <div v-if="state.phase === 'loading'" role="status" class="text-sm text-muted-foreground">{{ translate('apfSoftware.loading') }}</div>
    <template v-else>
      <div v-if="software" class="flex min-h-12 flex-wrap items-center gap-2 rounded-md px-2 text-sm hover:bg-interface-menu-component-surface-hovered">
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
        <span class="text-xs text-muted-foreground">{{ translate('apfSoftware.bundleLabel') }} {{ software.bundle_version ?? translate(installed ? 'apfSoftware.versionUnknown' : 'apfSoftware.notInstalled') }} · {{ translate('apfSoftware.programVersion') }} {{ software.installed_version ?? translate(installed ? 'apfSoftware.versionUnknown' : 'apfSoftware.notInstalled') }}</span>
        <div v-if="software.development_source" data-testid="development-source" class="basis-full text-xs break-all text-muted-foreground">
          <strong>{{ translate('apfSoftware.developmentSource') }}</strong>
          · {{ translate('apfSoftware.developmentState.' + software.development_source.state) }}
          · {{ software.development_source.bundle_version }} / {{ software.development_source.software_version }}
          <div>{{ software.development_source.root }}</div>
          <div>{{ translate('apfSoftware.developmentHead') }} {{ software.development_source.head }} · {{ translate(software.development_source.dirty ? 'apfSoftware.developmentDirty' : 'apfSoftware.developmentClean') }}</div>
          <div>{{ translate('apfSoftware.developmentFingerprint') }} {{ software.development_source.fingerprint }}</div>
          <div v-if="software.development_source.error" role="alert">{{ software.development_source.error }}</div>
        </div>
        <div class="flex min-w-0 basis-full items-center gap-2">
          <component
            :is="controls.select" v-if="controls?.select" :model-value="selectedValue" :options="versionOptions"
            :label="translate('apfSoftware.bundleVersion')" :disabled="busy" size="md" class="min-w-0 flex-1"
            popover-max-width="min(560px, calc(100vw - 32px))" @update:model-value="changeSelection" />
          <select v-else :value="selectedValue" :aria-label="translate('apfSoftware.bundleVersion')" :disabled="busy" class="min-w-0 flex-1" @change="selectNative">
            <option v-if="!selectedValue" value="" disabled>{{ translate('apfSoftware.selectVersion') }}</option>
            <option v-for="version in versionOptions" :key="version.value" :value="version.value" :disabled="version.disabled">{{ version.name }}</option>
          </select>
          <component :is="controls?.button ?? 'button'" type="button" size="sm" variant="textonly" data-testid="refresh-versions" :disabled="releasesLoading" @click="refreshReleases">{{ translate('apfSoftware.refreshVersions') }}</component>
        </div>
        <component
          :is="controls?.button ?? 'button'"
          type="button" size="sm" variant="primary" class="h-8 shrink-0"
          :disabled="busy || software.operation_state === 'unknown' || !canInstallSelection"
          :data-testid="installed ? 'request-update' : 'request-install'" @click="requestAction(installed ? 'update' : 'install')"
        >{{ translate(installed ? 'apfSoftware.switchVersion' : 'apfSoftware.install') }}</component>
        <component
          :is="controls?.button ?? 'button'" v-if="uninstallAction"
          type="button" size="sm" :variant="uninstallAction ? 'secondary' : 'primary'"
          class="h-8 shrink-0" :disabled="busy || software.operation_state === 'unknown'"
          :loading="busy" :data-testid="uninstallAction ? 'request-uninstall' : 'request-install'" @click="requestAction(uninstallAction ? 'uninstall' : 'install')"
        >{{ translate(uninstallAction ? 'apfSoftware.uninstall' : 'apfSoftware.install') }}</component>
      </div>
      <component :is="controls?.button ?? 'button'" v-if="action?.state === 'awaiting_confirmation'" type="button" size="sm" variant="textonly" @click="planOpen = true">{{ translate('apfSoftware.reviewPlan') }}</component>
      <p v-if="releasesLoading" role="status" class="px-2 text-xs">{{ translate('apfSoftware.checkingVersions') }}</p>
      <p v-if="releases?.checked_at" class="px-2 text-xs text-muted-foreground">{{ translate('apfSoftware.versionsCheckedAt') }} {{ new Date(releases.checked_at).toLocaleString() }}</p>
      <p v-if="releasesFailure || releases?.error" role="alert" class="px-2 text-xs text-error">{{ translate(releases?.error?.code === 'RELEASE_CHECK_BUSY' ? 'apfSoftware.releaseCheckBusy' : 'apfSoftware.releaseCheckFailed') }}</p>
      <details v-if="releases?.error?.fields.length" class="px-2 text-xs"><summary>{{ translate('apfSettings.diagnostics') }}</summary><p v-for="(field, index) in releases.error.fields" :key="index" class="break-all">{{ field.message }}</p></details>
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
      :title="translate(action.plan.action === 'uninstall' ? 'apfSoftware.confirmUninstall' : action.plan.action === 'update' ? 'apfSoftware.confirmSwitchVersion' : 'apfSoftware.confirmInstall')"
      data-testid="software-plan" @close="planOpen = false"
    >
      <div class="flex min-h-0 flex-col gap-3 overflow-y-auto p-4 text-sm">
        <div class="font-medium">{{ software?.name }} {{ action.plan.target_version ?? action.plan.current_version }}</div>
        <p>{{ translate('apfSoftware.bundleLabel') }} {{ action.plan.current_bundle_version ?? translate('apfSoftware.notInstalled') }} → {{ action.plan.target_bundle_version ?? translate('apfSoftware.notInstalled') }}</p>
        <p v-if="action.plan.target_tag" class="break-all">{{ action.plan.target_tag }} · {{ action.plan.target_commit }}</p>
        <p v-if="action.plan.restart_required">{{ action.plan.restart_reason }}</p>
          <p v-if="action.plan.action === 'uninstall'">{{ translate('apfSoftware.uninstallNotice') }}</p>
        <template v-else>
          <a v-if="action.plan.source" :href="action.plan.source.split(' @ ')[0]" target="_blank" rel="noreferrer" class="break-all underline">{{ action.plan.source }}</a>
          <p class="break-all">{{ action.plan.install_path }}</p>
          <details v-if="action.plan.node_changes.length"><summary>{{ translate('apfSoftware.nodeChanges') }} ({{ action.plan.node_changes.length }})</summary><p v-for="node in action.plan.node_changes" :key="node.definition_id">{{ translate('apfSoftware.nodeAction.' + node.action) }} · {{ node.name }}</p></details>
        </template>
        <p v-if="!confirmationAvailable" role="status">{{ translate('apfSoftware.confirmationUnavailable') }}</p>
        <p v-if="'error' in state && state.error" role="alert" class="text-error">{{ state.error }}</p>
      </div>
      <div class="flex shrink-0 justify-end gap-2 border-t border-interface-stroke p-3">
        <component :is="controls?.button ?? 'button'" type="button" size="sm" variant="secondary" :disabled="state.phase === 'confirming'" @click="planOpen = false">{{ translate('apfSoftware.cancel') }}</component>
        <component :is="controls?.button ?? 'button'" type="button" size="sm" variant="primary" :disabled="busy || !confirmationAvailable" data-testid="confirm-software" @click="confirmAction">{{ translate(action.plan.action === 'uninstall' ? 'apfSoftware.uninstall' : action.plan.action === 'update' ? 'apfSoftware.switchVersion' : 'apfSoftware.install') }}</component>
      </div>
    </component>
  </section>
</template>
