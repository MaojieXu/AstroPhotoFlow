<script setup lang="ts">
import {
  AnalysisView,
  createRunResultClient,
  runCallResultSchema,
  runOutputBase,
  runResultBase
} from '@astrophotoflow/ui'
import type {
  AnalysisResult,
  MediaSelection,
  MediaViewerRequest,
  RunCallResult
} from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import type { ComponentWidget } from '@/scripts/domWidget'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'

import MediaViewer from './MediaViewer.vue'
import MediaImagePreview from './MediaImagePreview.vue'
import { bundleCapabilities } from './bundleCatalog'
import { automaticResultState, retryAutomaticResult, setAutomaticResult } from './useAutomaticResults'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const outputs = useNodeOutputStore()
const outputIndex = ref(0)
const memberIndex = ref(0)
const analyses = ref<AnalysisResult[]>([])
const loading = ref(false)
const failure = ref('')
const viewer = ref<MediaViewerRequest>()
let controller: AbortController | undefined
let generation = 0

const automatic = computed(() => automaticResultState(widget.node))
const supportsAutomatic = computed(() => !!bundleCapabilities.get(widget.node.comfyClass ?? '')?.automatic_result_preview)
const automaticEnabled = computed(() => { void automatic.value; return widget.node.properties.apfAutomaticResult !== false })
const lastResult = shallowRef<RunCallResult>()
watch(() => outputs.getNodeOutputs(widget.node)?.apf_result, values => {
  if (!Array.isArray(values)) return
  const parsed = runCallResultSchema.safeParse(values.at(-1))
  if (!parsed.success || parsed.data.workflow_id !== widget.node.graph?.rootGraph.id) return
  if (parsed.data.calculation_signature && parsed.data.calculation_signature !== automatic.value?.submitted) return
  lastResult.value = parsed.data
}, { immediate: true })
const result = computed(() => lastResult.value?.workflow_id === widget.node.graph?.rootGraph.id ? lastResult.value : undefined)
const stale = computed(() => result.value?.calculation_signature && result.value.calculation_signature !== automatic.value?.signature)
const port = computed(() => result.value?.ports[outputIndex.value])
const hasFile = computed(() => !!port.value && port.value.members > 0)
const canView = computed(
  () =>
    hasFile.value &&
    ['fits', 'xisf', 'image', 'raw', 'video', 'numpy'].includes(
      port.value?.formats[memberIndex.value] ?? ''
    )
)
const fileUrl = computed(() =>
  result.value && hasFile.value
    ? runOutputBase(result.value, outputIndex.value, memberIndex.value) +
      '/file'
    : ''
)
const logUrl = computed(() =>
  result.value ? runResultBase(result.value) + '/log' : ''
)
const labels = computed(() => ({
  unavailable: t('astrophotoflow.results.unavailable'),
  logarithmic: t('astrophotoflow.results.logarithmic'),
  source: t('astrophotoflow.results.source'),
  unit: t('astrophotoflow.results.unit'),
  chart: t('astrophotoflow.results.chart')
}))

async function loadAnalysis() {
  const current = ++generation
  controller?.abort()
  controller = new AbortController()
  const signal = controller.signal
  analyses.value = []
  failure.value = ''
  const snapshot = result.value
  if (!snapshot || !hasFile.value || port.value?.type !== 'APF_ANALYSIS') {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const client = createRunResultClient((path, init) =>
      fetch(path, { ...init, signal })
    )
    const values = await client.analysis(
      snapshot,
      outputIndex.value,
      memberIndex.value
    )
    if (current === generation && !signal.aborted) analyses.value = values
  } catch (cause) {
    if (current === generation && !signal.aborted)
      failure.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    if (current === generation) loading.value = false
  }
}

function openViewer(selection: Partial<MediaSelection> = {}) {
  const snapshot: RunCallResult | undefined = result.value
  const selected = port.value
  const selectedOutput = outputIndex.value
  if (!snapshot || !selected || !canView.value) return
  viewer.value = {
    index: memberIndex.value,
    total: selected.members,
    member: async (index) => ({
      title: `${widget.node.title} · ${selected.name} · ${index + 1} · ${snapshot.prompt_id.slice(0, 8)}`,
      basePath: runOutputBase(snapshot, selectedOutput, index), selection
    })
  }
}

watch(
  () => result.value?.call_id,
  () => {
    outputIndex.value = 0
    memberIndex.value = 0
  }
)
watch(outputIndex, () => {
  memberIndex.value = 0
})
watch(
  () => [result.value?.call_id, outputIndex.value, memberIndex.value],
  loadAnalysis,
  { immediate: true }
)
onBeforeUnmount(() => {
  generation++
  controller?.abort()
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
    <label v-if="supportsAutomatic" class="flex items-center gap-2"><input type="checkbox" :checked="automaticEnabled" @change="setAutomaticResult(widget.node, !automaticEnabled)" />{{ t('astrophotoflow.results.automatic') }}</label>
    <p v-if="automatic" :role="automatic.phase === 'failed' ? 'alert' : 'status'" class="m-0 wrap-break-word text-muted-foreground">{{ t(`astrophotoflow.results.auto_${stale && automatic.phase === 'completed' ? 'waiting' : automatic.phase}`) }}<span v-if="automatic.error"> · {{ automatic.error }}</span><Button v-if="automatic.phase === 'failed'" size="sm" variant="textonly" @click="retryAutomaticResult(widget.node)">{{ t('g.retry') }}</Button></p>
    <p v-if="!result && !automatic" class="m-0 text-muted-foreground">
      {{ t('astrophotoflow.results.runFirst') }}
    </p>
    <template v-if="result">
      <p v-if="stale" class="m-0 text-muted-foreground">{{ t('astrophotoflow.results.previousResult') }}</p>
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
              {{ item.name }} ({{ item.members }})
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
        <span class="max-w-full truncate" :title="port?.names[memberIndex]">{{
          port?.names[memberIndex]
        }}</span>
        <Button
          v-if="port && port.members > 1"
          size="icon"
          variant="textonly"
          :disabled="memberIndex === 0"
          :aria-label="t('g.previous')"
          @click="memberIndex--"
          ><i class="icon-[lucide--chevron-left] size-4"
        /></Button>
        <span class="tabular-nums"
          >{{ memberIndex + 1 }} / {{ port?.members }}</span
        >
        <Button
          v-if="port && port.members > 1"
          size="icon"
          variant="textonly"
          :disabled="memberIndex + 1 === port.members"
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
      <MediaImagePreview v-if="canView && result" :key="`${result.call_id}:${outputIndex}:${memberIndex}`" :base="runOutputBase(result, outputIndex, memberIndex)" :title="port?.names[memberIndex] ?? ''" @open="openViewer" />
      <p v-if="loading" role="status" class="m-0 text-muted-foreground">
        {{ t('astrophotoflow.results.loading') }}
      </p>
      <p v-if="failure" role="alert" class="m-0 wrap-break-word text-error">
        {{ failure
        }}<Button size="sm" variant="textonly" @click="loadAnalysis">{{
          t('g.retry')
        }}</Button>
      </p>
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
