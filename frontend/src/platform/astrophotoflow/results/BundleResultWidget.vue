<script setup lang="ts">
import {
  AnalysisView,
  createRunResultClient,
  useCallAnalysis,
  useSoftwareCall,
  softwareCallResultSchema
} from '@astrophotoflow/ui'
import type {
  MediaSelection,
  MediaViewerRequest,
  SoftwareCallResult
} from '@astrophotoflow/ui'
import { computed, ref, shallowRef, watch } from 'vue'
import { useNativeWorkspace } from '../useNativeWorkspace'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import type { ComponentWidget } from '@/scripts/domWidget'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'

import MediaViewer from '../media/MediaViewer.vue'
import MediaImagePreview from '../media/MediaImagePreview.vue'
import { bundleCapabilities } from '../sidebar/bundleCatalog'
import {
  automaticResultState,
  retryAutomaticResult,
  setAutomaticResult
} from './automatic'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const outputs = useNodeOutputStore()
const outputIndex = ref(0)
const memberIndex = ref(0)
const viewer = ref<MediaViewerRequest>()
const workspace = useNativeWorkspace()
const client = createRunResultClient((path, init) => fetch(path, init))
const automatic = computed(() => automaticResultState(widget.node))
const supportsAutomatic = computed(
  () =>
    !!bundleCapabilities.get(widget.node.comfyClass ?? '')
      ?.automatic_result_preview
)
const automaticEnabled = computed(() => {
  void automatic.value
  return widget.node.properties.apfAutomaticResult !== false
})
const lastResult = shallowRef<SoftwareCallResult>()
watch(
  () => outputs.getNodeOutputs(widget.node)?.apf_result,
  (values) => {
    if (!Array.isArray(values)) return
    const parsed = softwareCallResultSchema.safeParse(values.at(-1))
    if (
      !parsed.success ||
      parsed.data.workflow_id !== widget.node.graph?.rootGraph.id
    )
      return
    if (
      parsed.data.calculation_signature &&
      parsed.data.calculation_signature !== automatic.value?.submitted
    )
      return
    lastResult.value = parsed.data
  },
  { immediate: true }
)
const candidate = computed(() =>
  lastResult.value?.workflow_id === widget.node.graph?.rootGraph.id
    ? lastResult.value
    : undefined
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
const result = computed(() =>
  workspace.workspaceId.value &&
  call.data.value &&
  candidate.value &&
  call.data.value.prompt_id === candidate.value.prompt_id &&
  call.data.value.call_id === candidate.value.call_id
    ? call.data.value
    : undefined
)
watch(workspace.workspaceId, () => {
  viewer.value = undefined
})
const stale = computed(
  () =>
    result.value?.calculation_signature &&
    result.value.calculation_signature !== automatic.value?.signature
)
const port = computed(() => result.value?.ports[outputIndex.value])
const hasFile = computed(() => !!port.value && port.value.members.length > 0)
const canView = computed(
  () =>
    hasFile.value &&
    ['fits', 'xisf', 'image', 'raw', 'video', 'numpy'].includes(
      port.value?.members[memberIndex.value]?.format ?? ''
    )
)
const selectedMember = computed(() => port.value?.members[memberIndex.value])
const fileUrl = computed(() => selectedMember.value?.file_url ?? '')
const logUrl = computed(() => result.value?.log_url ?? '')
const labels = computed(() => ({
  unavailable: t('astrophotoflow.results.unavailable'),
  logarithmic: t('astrophotoflow.results.logarithmic'),
  source: t('astrophotoflow.results.source'),
  unit: t('astrophotoflow.results.unit'),
  chart: t('astrophotoflow.results.chart')
}))

const analysis = useCallAnalysis(() =>
  workspace.workspaceId.value &&
  result.value &&
  hasFile.value &&
  port.value?.type === 'APF_ANALYSIS'
    ? {
        workspaceId: workspace.workspaceId.value,
        client,
        result: result.value,
        outputIndex: outputIndex.value,
        memberIndex: memberIndex.value
      }
    : undefined
)
const analyses = computed(() =>
  workspace.workspaceId.value && port.value?.type === 'APF_ANALYSIS'
    ? (analysis.data.value ?? [])
    : []
)
const loading = computed(
  () =>
    (!workspace.ready.value && !workspace.error.value) ||
    call.isFetching.value ||
    analysis.isFetching.value
)
const failure = computed(
  () =>
    workspace.error.value?.message ??
    call.error.value?.message ??
    analysis.error.value?.message ??
    ''
)

function retry() {
  if (workspace.error.value) return workspace.refresh()
  if (call.error.value) return call.refetch()
  return analysis.refetch()
}

function openViewer(selection: Partial<MediaSelection> = {}) {
  const snapshot: SoftwareCallResult | undefined = result.value
  const selected = port.value
  if (!snapshot || !selected || !canView.value) return
  viewer.value = {
    index: memberIndex.value,
    total: selected.members.length,
    member: async (index) => ({
      title: `${widget.node.title} · ${selected.name} · ${index + 1} · ${snapshot.prompt_id.slice(0, 8)}`,
      basePath: selected.members[index]!.view_base,
      selection
    })
  }
}

watch(
  () => [result.value?.prompt_id, result.value?.call_id],
  () => {
    outputIndex.value = 0
    memberIndex.value = 0
  }
)
watch(outputIndex, () => {
  memberIndex.value = 0
})
</script>

<template>
  <div
    class="flex h-full min-w-0 flex-col gap-2 overflow-auto p-2 text-xs"
    @pointerdown.stop
    @pointermove.stop
    @pointerup.stop
    @keydown.stop
    @wheel.stop
  >
    <p class="m-0 font-medium">{{ t('astrophotoflow.results.title') }}</p>
    <label v-if="supportsAutomatic" class="flex items-center gap-2"
      ><input
        type="checkbox"
        :checked="automaticEnabled"
        @change="setAutomaticResult(widget.node, !automaticEnabled)"
      />{{ t('astrophotoflow.results.automatic') }}</label
    >
    <p
      v-if="automatic"
      :role="automatic.phase === 'failed' ? 'alert' : 'status'"
      class="m-0 wrap-break-word text-muted-foreground"
    >
      {{
        t(
          `astrophotoflow.results.auto_${stale && automatic.phase === 'completed' ? 'waiting' : automatic.phase}`
        )
      }}<span v-if="automatic.error"> · {{ automatic.error }}</span
      ><Button
        v-if="automatic.phase === 'failed'"
        size="sm"
        variant="textonly"
        @click="retryAutomaticResult(widget.node)"
        >{{ t('g.retry') }}</Button
      >
    </p>
    <p v-if="!result && !automatic" class="m-0 text-muted-foreground">
      {{ t('astrophotoflow.results.runFirst') }}
    </p>
    <p v-if="loading" role="status" class="m-0 text-muted-foreground">
      {{ t('astrophotoflow.results.loading') }}
    </p>
    <p v-if="failure" role="alert" class="m-0 wrap-break-word text-error">
      {{ failure
      }}<Button size="sm" variant="textonly" @click="retry">{{
        t('g.retry')
      }}</Button>
    </p>
    <template v-if="result">
      <p v-if="stale" class="m-0 text-muted-foreground">
        {{ t('astrophotoflow.results.previousResult') }}
      </p>
      <div class="flex flex-wrap items-center gap-1">
        <label class="flex min-h-8 min-w-0 flex-1 items-center gap-1"
          >{{ t('astrophotoflow.results.output')
          }}<select
            v-model.number="outputIndex"
            class="min-w-0 flex-1 rounded-sm border border-border-default bg-base-background p-1"
          >
            <option
              v-for="(item, index) in result.ports"
              :key="index"
              :value="index"
            >
              {{ item.name }} ({{ item.members.length }})
            </option>
          </select></label
        >
        <a
          :href="logUrl"
          download
          class="flex min-h-8 items-center underline"
          >{{ t('astrophotoflow.results.log') }}</a
        >
      </div>
      <div v-if="hasFile" class="flex flex-wrap items-center gap-1">
        <span class="max-w-full truncate" :title="selectedMember?.name">{{
          selectedMember?.name
        }}</span>
        <Button
          v-if="port && port.members.length > 1"
          size="icon"
          variant="textonly"
          :disabled="memberIndex === 0"
          :aria-label="t('g.previous')"
          @click="memberIndex--"
          ><i class="icon-[lucide--chevron-left] size-4"
        /></Button>
        <span class="tabular-nums"
          >{{ memberIndex + 1 }} / {{ port?.members.length }}</span
        >
        <Button
          v-if="port && port.members.length > 1"
          size="icon"
          variant="textonly"
          :disabled="memberIndex + 1 === port.members.length"
          :aria-label="t('g.next')"
          @click="memberIndex++"
          ><i class="icon-[lucide--chevron-right] size-4"
        /></Button>
        <Button
          v-if="canView"
          size="sm"
          variant="secondary"
          @click="openViewer()"
          >{{ t('astrophotoflow.media.open') }}</Button
        >
        <a
          :href="fileUrl"
          download
          class="ml-auto flex min-h-8 items-center underline"
          >{{ t('astrophotoflow.results.fullFile') }}</a
        >
      </div>
      <p v-else class="m-0 text-muted-foreground">
        {{ t('astrophotoflow.results.noOutput') }}
      </p>
      <MediaImagePreview
        v-if="canView && result"
        :key="`${result.call_id}:${outputIndex}:${memberIndex}`"
        :base="selectedMember?.view_base ?? ''"
        :title="selectedMember?.name ?? ''"
        @open="openViewer"
      />
      <AnalysisView
        v-for="(analysis, index) in analyses"
        :key="index"
        :result="analysis"
        :labels
      />
      <p
        v-if="result.preview_error"
        class="m-0 wrap-break-word text-muted-foreground"
      >
        {{ result.preview_error }}
      </p>
      <span class="text-muted-foreground"
        >{{ t('astrophotoflow.results.run') }}
        {{ result.prompt_id.slice(0, 8) }}</span
      >
    </template>
    <MediaViewer v-if="viewer" :request="viewer" @close="viewer = undefined" />
  </div>
</template>
