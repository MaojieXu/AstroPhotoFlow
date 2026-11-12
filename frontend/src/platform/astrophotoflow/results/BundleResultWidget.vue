<script setup lang="ts">
import {
  AnalysisView,
  createRunResultClient,
  useCallAnalysis,
  useSoftwareCall,
  softwareCallResultSchema
} from '@astrophotoflow/ui'
import type {
  AnalysisResult,
  MediaPosition,
  MediaSelection,
  MediaState,
  MediaViewerRequest,
  RunOutputPort,
  SoftwareCallResult
} from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSettingStore } from '@/platform/settings/settingStore'
import { api } from '@/scripts/api'
import type { ComponentWidget } from '@/scripts/domWidget'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'
import { useExecutionStore } from '@/stores/executionStore'
import { useExecutionErrorStore } from '@/stores/executionErrorStore'
import {
  executionIdToNodeLocatorId,
  getExecutionIdByNode
} from '@/utils/graphTraversalUtil'
import { bundleCapabilities, bundleNodeIssue } from '../sidebar/bundleCatalog'
import { useNativeWorkspace } from '../useNativeWorkspace'
import MediaViewer from '../media/MediaViewer.vue'
import MediaImagePreview from '../media/MediaImagePreview.vue'
import BundleInputEditor from './BundleInputEditor.vue'
import Button from '@/components/ui/button/Button.vue'
import Select from '@/components/ui/select/Select.vue'
import SelectTrigger from '@/components/ui/select/SelectTrigger.vue'
import SelectValue from '@/components/ui/select/SelectValue.vue'
import SelectContent from '@/components/ui/select/SelectContent.vue'
import SelectItem from '@/components/ui/select/SelectItem.vue'
import Menu from '@/components/ui/menu/Menu.vue'
import MenuItem from '@/components/ui/menu/MenuItem.vue'
import { useNodeWidgetSize } from '../canvas/useNodeWidgetSize'
import { automaticResultState, retryAutomaticResult } from './automatic'

type Channel = NonNullable<MediaSelection['channel']>
const viewable = new Set(['fits', 'xisf', 'image', 'raw', 'video', 'numpy'])
function mediaPort(port: RunOutputPort) {
  return (
    port.data_kind === 'image' ||
    port.data_kind === 'sequence' ||
    port.data_kind === 'video' ||
    (!port.data_kind && port.type === 'APF_SCIENCE')
  )
}
const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t, locale } = useI18n()
const outputs = useNodeOutputStore()
const execution = useExecutionStore()
const errors = useExecutionErrorStore()
const workspace = useNativeWorkspace()
const client = createRunResultClient((path, init) => fetch(path, init))
const settings = useSettingStore()
const edge = computed(
  () => settings.get('AstroPhotoFlow.ResultThumbnailSize') ?? 1024
)
const node = computed(() => widget.node)
const content = ref<HTMLElement>()
useNodeWidgetSize(() => widget, content)
const capability = computed(() =>
  bundleCapabilities.get(node.value.comfyClass ?? '')
)
const automatic = computed(() => automaticResultState(node.value))
const issue = computed(() => bundleNodeIssue(node.value))
const executionId = computed(() => {
  const graph = node.value.graph?.rootGraph
  return graph ? getExecutionIdByNode(graph, node.value) : undefined
})
const executing = computed(() => {
  const job = execution.activeJobId
  return Boolean(
    job &&
    executionId.value &&
    execution.jobIdToWorkflowId.get(job) === node.value.graph?.rootGraph.id &&
    execution.uniqueExecutingNodeIdStrings.has(executionId.value)
  )
})
const nativeFailure = computed(() => {
  const id = executionId.value
  const locator = id
    ? executionIdToNodeLocatorId(node.value.graph?.rootGraph, id)
    : undefined
  return locator && errors.lastExecutionErrorNodeLocatorId === locator
    ? errors.lastExecutionError?.exception_message
    : undefined
})
const nativeFailureType = computed(() => nativeFailure.value
  ? errors.lastExecutionError?.exception_type.split('.').at(-1) : undefined)
const needsObservation = computed(() =>
  ['SoftwareCallBlocked', 'SoftwareCallUnknown'].includes(nativeFailureType.value ?? ''))
const revision = ref(0)
const changed = () => {
  revision.value++
}
api.addEventListener('graphChanged', changed)
onBeforeUnmount(() => api.removeEventListener('graphChanged', changed))

const outputIndex = ref(0)
const memberIndex = ref(0)
const frameIndex = ref(0)
const channel = ref<Channel>('composite')
const mediaChannels = ref<Channel[]>([])
const frameCount = ref<number>()
const viewer = shallowRef<MediaViewerRequest>()
const editName = ref('')
const candidate = shallowRef<SoftwareCallResult>()
const result = shallowRef<SoftwareCallResult>()
const baseline = shallowRef<SoftwareCallResult>()

watch(
  [workspace.workspaceId, () => node.value.graph?.rootGraph.id],
  ([id, graph], [previous, previousGraph]) => {
    if ((id && previous && id !== previous) || graph !== previousGraph)
      candidate.value = undefined
    result.value = undefined
    baseline.value = undefined
    viewer.value = undefined
    editName.value = ''
  },
  { flush: 'sync' }
)

watch(
  () => outputs.getNodeOutputs(node.value)?.apf_result,
  (values) => {
    if (!Array.isArray(values)) return
    const parsed = softwareCallResultSchema.safeParse(values.at(-1))
    if (
      !parsed.success ||
      parsed.data.workflow_id !== node.value.graph?.rootGraph.id
    )
      return
    if (
      parsed.data.calculation_signature &&
      parsed.data.calculation_signature !== automatic.value?.submitted
    )
      return
    candidate.value = parsed.data
  },
  { immediate: true }
)

const call = useSoftwareCall(() =>
  workspace.workspaceId.value && candidate.value
    ? {
        workspaceId: workspace.workspaceId.value,
        client,
        result: candidate.value
      }
    : undefined
)
const pending = computed(() =>
  call.data.value?.call_id === candidate.value?.call_id &&
  call.data.value?.prompt_id === candidate.value?.prompt_id
    ? call.data.value
    : undefined
)

function comparable(before: SoftwareCallResult, after: SoftwareCallResult) {
  return Boolean(
    before.input_token &&
    before.input_token === after.input_token &&
    before.package_id === after.package_id &&
    before.operation_id === after.operation_id &&
    before.definition_token === after.definition_token &&
    before.bundle_commit === after.bundle_commit &&
    before.bundle_version === after.bundle_version &&
    before.development_source?.fingerprint ===
      after.development_source?.fingerprint
  )
}

function firstOutput(value: SoftwareCallResult) {
  const preferred = value.ports.findIndex(
    (port) => port.role === 'result' && port.members.length
  )
  if (preferred !== -1) return preferred
  const image = value.ports.findIndex(
    (port) =>
      mediaPort(port) &&
      port.members.some((member) => viewable.has(member.format))
  )
  if (image !== -1) return image
  return Math.max(
    0,
    value.ports.findIndex((port) => port.members.length)
  )
}

watch(
  pending,
  (next) => {
    if (
      !workspace.workspaceId.value ||
      !next ||
      next.state !== 'completed' ||
      (next.call_id === result.value?.call_id &&
        next.prompt_id === result.value.prompt_id)
    )
      return
    const before = result.value
    if (!before || !comparable(before, next)) {
      baseline.value = undefined
      outputIndex.value = firstOutput(next)
      memberIndex.value = 0
      frameIndex.value = 0
    channel.value = 'composite'
    } else {
      baseline.value ??= before
      if (!next.ports[outputIndex.value]?.members[memberIndex.value]) {
        outputIndex.value = firstOutput(next)
        memberIndex.value = 0
        frameIndex.value = 0
      }
    }
    result.value = next
  },
  { immediate: true }
)

const stale = computed(() =>
  Boolean(
    result.value &&
    (executing.value ||
      nativeFailure.value ||
      (candidate.value &&
        (result.value.call_id !== candidate.value.call_id ||
          result.value.prompt_id !== candidate.value.prompt_id)) ||
      (result.value.calculation_signature &&
        automatic.value?.signature &&
        result.value.calculation_signature !== automatic.value.signature))
  )
)
const failure = computed(
  () =>
    workspace.error.value?.message ??
    call.error.value?.message ??
    pending.value?.error?.message ??
    automatic.value?.error ??
    nativeFailure.value ??
    ''
)
const logUrl = computed(() => pending.value?.log_url ?? result.value?.log_url)
const port = computed(() => result.value?.ports[outputIndex.value])
const selectedMember = computed(() => port.value?.members[memberIndex.value])
const canView = computed(() =>
  Boolean(
    port.value &&
    mediaPort(port.value) &&
    selectedMember.value &&
    viewable.has(selectedMember.value.format)
  )
)
const memberFrames = computed(
  () => frameCount.value ?? selectedMember.value?.frame_count ?? 0
)
const viewSelection = computed<Partial<MediaSelection>>(() => ({
  channel: channel.value,
  frame_index: frameIndex.value,
  preview_max_edge: edge.value,
  hdu_index: memberFrames.value > 1 ? undefined : selectedMember.value?.hdu_index,
  display_balance: 'preserve'
}))
const labels = computed(() => ({
  unavailable: t('astrophotoflow.results.unavailable'),
  logarithmic: t('astrophotoflow.results.logarithmic'),
  source: t('astrophotoflow.results.source'),
  unit: t('astrophotoflow.results.unit'),
  chart: t('astrophotoflow.results.chart'),
  before: t('astrophotoflow.bundle.before'),
  current: t('astrophotoflow.bundle.current'),
  frame: t('astrophotoflow.bundle.frame')
}))
const status = computed(() => {
  if (issue.value) return t(issue.value)
  if (capability.value?.available === false)
    return capability.value.reason ?? t('apfSoftware.unavailable')
  if (nativeFailureType.value === 'SoftwareCallBlocked') return t('astrophotoflow.bundle.blocked')
  if (nativeFailureType.value === 'SoftwareCallUnknown') return t('astrophotoflow.bundle.unknown')
  if (nativeFailure.value) return t('astrophotoflow.bundle.failed')
  if (executing.value) return t('astrophotoflow.bundle.running')
  if (
    automatic.value &&
    automatic.value.phase !== 'completed' &&
    (stale.value || !result.value)
  ) {
    if (automatic.value.phase === 'manual') return t('astrophotoflow.results.auto_paused')
    if (automatic.value.phase === 'running') return t('astrophotoflow.bundle.running')
    return t('astrophotoflow.results.auto_' + automatic.value.phase)
  }
  if (pending.value && pending.value.state !== 'completed')
    return t('astrophotoflow.bundle.' + pending.value.state)
  return result.value && !stale.value
    ? t('astrophotoflow.bundle.completed')
    : call.isFetching.value
      ? t('astrophotoflow.media.preparing')
      : t('astrophotoflow.bundle.waiting')
})

function outputTitle(value: RunOutputPort) {
  const name = Object.entries(capability.value?.node.definition.execution.outputs ?? {})
    .find(([, operationName]) => operationName === value.name)?.[0] ?? value.name
  return (
    capability.value?.display?.[locale.value as 'en' | 'zh']?.outputs?.[
      name
    ]?.label ?? name
  )
}

function analysisAddress(value: SoftwareCallResult) {
  const selected = value.ports[outputIndex.value]
  const index =
    selected?.type === 'APF_ANALYSIS'
      ? outputIndex.value
      : value.ports.findIndex(
          (item) => item.type === 'APF_ANALYSIS' && item.members.length
        )
  const reports = value.ports[index]
  if (!reports?.members.length) return
  const member =
    selected?.type === 'APF_ANALYSIS' ||
    reports.members.length === selected?.members.length
      ? memberIndex.value
      : 0
  if (reports.members[member])
    return { outputIndex: index, memberIndex: member }
}
function analysisRequest(value?: SoftwareCallResult) {
  const workspaceId = workspace.workspaceId.value
  const address = value && analysisAddress(value)
  return workspaceId && value && address
    ? { workspaceId, client, result: value, ...address }
    : undefined
}
const analysis = useCallAnalysis(() => analysisRequest(result.value))
const olderAnalysis = useCallAnalysis(() => analysisRequest(baseline.value))
const reported = computed(() =>
  (analysis.data.value ?? []).filter((item) => {
    if (item.histogram && item.histogram.channel !== channel.value) return false
    if (port.value?.type === 'APF_ANALYSIS') return true
    return (
      (!item.output ||
        item.output === port.value?.operation_output ||
        item.output === port.value?.name) &&
      (item.member_index == null || item.member_index === memberIndex.value) &&
      (item.frame_index == null || item.frame_index === frameIndex.value)
    )
  })
)
const channels = computed(() => {
  const values = new Set<Channel>(mediaChannels.value)
  if (!canView.value) {
    for (const item of analysis.data.value ?? [])
      if (item.histogram) values.add(item.histogram.channel)
  }
  return (['composite', 'red', 'green', 'blue'] as const).filter((value) =>
    values.has(value)
  )
})

watch(channels, (values) => {
  if (values.length && !values.includes(channel.value))
    channel.value = values[0]!
})

function matchingBaseline(item: AnalysisResult) {
  if (!item.histogram || stale.value) return
  return olderAnalysis.data.value?.find(
    (before) =>
      before.histogram &&
      before.title === item.title &&
      before.source === item.source &&
      before.unit === item.unit &&
      before.sample === item.sample &&
      before.output === item.output &&
      before.member_index === item.member_index &&
      before.frame_index === item.frame_index &&
      before.histogram.channel === item.histogram?.channel &&
      before.histogram.intensity_unit === item.histogram.intensity_unit &&
      before.histogram.edges.length === item.histogram.edges.length &&
      before.histogram.edges.every(
        (edge, index) => edge === item.histogram?.edges[index]
      )
  )
}

function changeOutput(index: number) {
  outputIndex.value = index
  memberIndex.value = 0
  frameIndex.value = 0
  channel.value = 'composite'
}
function changeMember(index: number) {
  memberIndex.value = index
  frameIndex.value = 0
  channel.value = 'composite'
}
watch(
  () => selectedMember.value?.view_base,
  () => {
    frameCount.value = undefined
    mediaChannels.value = []
  }
)
function receivedMedia(state: MediaState) {
  frameCount.value = state.frame_count ?? undefined
  mediaChannels.value = state.channels ?? []
}

function targetOutput(report: AnalysisResult) {
  if (!report.output) return -1
  return (
    result.value?.ports.findIndex(
      (item) =>
        mediaPort(item) &&
        (item.operation_output ?? item.name) === report.output &&
        item.members.some((member) => viewable.has(member.format))
    ) ?? -1
  )
}
function selectFrame(report: AnalysisResult, position: MediaPosition) {
  const index = targetOutput(report)
  const member = result.value?.ports[index]?.members[position.member_index]
  if (
    !member ||
    (position.frame_index ?? 0) >= (member.frame_count ?? Infinity)
  )
    return
  if (index !== outputIndex.value) changeOutput(index)
  if (position.member_index !== memberIndex.value)
    changeMember(position.member_index)
  frameIndex.value = position.frame_index ?? 0
}

function openViewer(selection: Partial<MediaSelection>) {
  const selected = port.value
  if (!selected || !canView.value) return
  const index = memberIndex.value
  viewer.value = {
    index,
    total: selected.members.length,
    fixedDisplay: true,
    member: async (position) => ({
      title: selected.members[position]!.name,
      basePath: selected.members[position]!.view_base,
      selection:
        position === index
          ? selection
          : {
              ...selection,
              channel: 'composite',
              frame_index: 0,
              hdu_index: selected.members[position]!.hdu_index
            }
    })
  }
}

const editorFields = computed(() => {
  const definition = capability.value?.node.definition
  const operation = capability.value?.operation
  if (!definition || !operation) return []
  return definition.parameters.flatMap((parameter) => {
    const operationParameter = operation.parameters.find((p) => {
      const binding = definition.execution.parameters[p.name]
      return (
        binding?.kind === 'parameter' &&
        binding.name === parameter.name &&
        p.editor
      )
    })
    const editor = operationParameter?.editor
    if (!editor) return []
    const input = editor.input
      ? definition.execution.inputs[editor.input]
      : undefined
    return [{ parameter: { ...parameter, editor }, input }]
  })
})
const activeEditor = computed(() =>
  editorFields.value.find((field) => field.parameter.name === editName.value)
)
function editorLabel(name: string) {
  return (
    capability.value?.display?.[locale.value as 'en' | 'zh']?.parameters?.[name]
      ?.label ?? name
  )
}
</script>

<template>
  <div
    data-testid="bundle-result-card"
    class="min-w-0 text-xs"
    @pointerdown.stop
    @pointermove.stop
    @pointerup.stop
    @keydown.stop
    @wheel.stop
  >
    <div ref="content" class="flex min-w-0 flex-col gap-2 p-2">
    <div class="flex items-center gap-2">
      <Select v-if="channels.length > 1" :model-value="channel" @update:model-value="channel = $event as Channel">
        <SelectTrigger data-testid="node-channel-select" size="md" class="w-28" :aria-label="t('astrophotoflow.bundle.channel')"><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem v-for="value in channels" :key="value" :value="value">{{ t('astrophotoflow.bundle.channels.' + value) }}</SelectItem></SelectContent>
      </Select>
      <span role="status" class="ml-auto text-muted-foreground">{{ status }}</span>
      <Menu v-if="logUrl || selectedMember" align="end">
        <template #trigger><Button variant="textonly" size="icon-sm" :aria-label="t('astrophotoflow.nodeUi.more')"><i class="icon-[lucide--ellipsis] size-4" aria-hidden="true" /></Button></template>
        <MenuItem v-if="logUrl" as-child><a :href="logUrl" download>{{ t('astrophotoflow.results.log') }}</a></MenuItem>
        <MenuItem v-if="selectedMember" as-child><a :href="selectedMember.file_url" :title="selectedMember.name" download>{{ t('astrophotoflow.results.fullFile') }}</a></MenuItem>
      </Menu>
    </div>
    <p v-if="failure" role="alert" class="m-0 wrap-break-word text-destructive">
      {{ failure }}
    </p>
    <Button variant="textonly" size="sm"
      v-if="
        !needsObservation && (call.error.value ||
        workspace.error.value ||
        automatic?.phase === 'failed')
      "
      type="button"
      class="self-start underline"
      @click="
        workspace.error.value
          ? workspace.refresh()
          : call.error.value
            ? call.refetch()
            : retryAutomaticResult(node)
      "
    >
      {{ t('g.retry') }}
    </Button>
    <div v-if="editorFields.length" class="flex flex-wrap gap-2">
      <Button variant="secondary" size="sm"
        v-for="field in editorFields"
        :key="field.parameter.name"
        type="button"
        :disabled="!!issue"
        class="rounded border border-border-default px-2 py-1"
        :aria-pressed="editName === field.parameter.name"
        @click="
          editName =
            editName === field.parameter.name ? '' : field.parameter.name
        "
      >
        {{ editorLabel(field.parameter.name) }}
      </Button>
      <Button variant="textonly" size="sm"
        v-if="activeEditor"
        type="button"
        class="ml-auto underline"
        @click="editName = ''"
      >
        {{ t('g.back') }}
      </Button>
    </div>
    <BundleInputEditor
      v-if="activeEditor"
      :key="activeEditor.parameter.name"
      :node="node"
      :parameter="activeEditor.parameter"
      :input="activeEditor.input"
      :revision="revision"
      :edge="edge"
    />
    <template v-else-if="result">
      <div class="flex flex-wrap items-center gap-2">
        <span
          v-if="stale"
          class="rounded bg-component-node-widget-background px-2 py-1 text-muted-foreground"
        >
          {{ t('astrophotoflow.bundle.previousResult') }}
        </span>
        <label v-if="result.ports.length > 1" class="flex items-center gap-1">
          {{ t('astrophotoflow.results.output') }}
          <select
            class="min-w-0 rounded bg-component-node-widget-background"
            :value="outputIndex"
            @change="
              changeOutput(Number(($event.target as HTMLSelectElement).value))
            "
          >
            <option
              v-for="(output, index) in result.ports"
              :key="output.name"
              :value="index"
            >
              {{ outputTitle(output) }}
            </option>
          </select>
        </label>
      </div>
      <div v-if="selectedMember" class="flex flex-wrap items-center gap-2">
        <label v-if="(port?.members.length ?? 0) > 1"
          >{{ t('astrophotoflow.bundle.member') }}
          <select
            class="max-w-28 rounded bg-component-node-widget-background"
            :value="memberIndex"
            @change="
              changeMember(Number(($event.target as HTMLSelectElement).value))
            "
          >
            <option
              v-for="(item, index) in port?.members"
              :key="item.view_base"
              :value="index"
            >
              {{ index + 1 }}
            </option>
          </select>
        </label>
        <label v-if="memberFrames > 1 || selectedMember.format === 'video'"
          >{{ t('astrophotoflow.bundle.frame') }}
          <input
            class="w-16 rounded bg-component-node-widget-background"
            type="number"
            min="1"
            :max="memberFrames || undefined"
            :value="frameIndex + 1"
            @change="
              frameIndex = Math.max(
                0,
                Math.min(
                  (memberFrames || Infinity) - 1,
                  Math.trunc(
                    Number(($event.target as HTMLInputElement).value)
                  ) - 1
                )
              )
            "
          />
        </label>
      </div>
      <p v-else class="m-0 text-muted-foreground">
        {{ t('astrophotoflow.results.noOutput') }}
      </p>
      <MediaImagePreview
        v-if="canView && selectedMember"
        :key="selectedMember.view_base"
        :base="selectedMember.view_base"
        :title="selectedMember.name"
        :selection="viewSelection"
        @media="receivedMedia"
        @open="openViewer"
      />
      <AnalysisView
        v-for="(report, index) in reported"
        :key="index"
        :result="report"
        :labels="labels"
        :baseline="matchingBaseline(report)"
        :selectable="targetOutput(report) >= 0"
        :position="{ member_index: memberIndex, frame_index: frameIndex }"
        @select="selectFrame(report, $event)"
      />
      <p v-if="analysis.error.value" role="alert" class="m-0 text-destructive">
        {{ analysis.error.value.message }}
      </p>
    </template>
    <MediaViewer v-if="viewer" :request="viewer" @close="viewer = undefined" />
    </div>
  </div>
</template>
