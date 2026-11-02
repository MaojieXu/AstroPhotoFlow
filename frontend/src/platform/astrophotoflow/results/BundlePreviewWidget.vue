<script setup lang="ts">
import {
  createBundlePreviewClient,
  scienceReferenceSchema,
  bundlePreviewRequestSchema,
  useBundleSamplePreview
} from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import ImagePreview from '@/renderer/extensions/vueNodes/components/ImagePreview.vue'
import { api } from '@/scripts/api'
import type { ComponentWidget } from '@/scripts/domWidget'
import { bundleCapabilities } from '../sidebar/bundleCatalog'
import PreviewControls from '../media/PreviewControls.vue'
import { useNativeWorkspace } from '../useNativeWorkspace'
import type { BundleSampleRequest, MediaSelection } from '@astrophotoflow/ui'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const tabs = useSidebarTabStore()
const revision = ref(0)
const index = ref(0)
const expanded = ref(false)
const maxEdge = ref<MediaSelection['preview_max_edge']>(1024)
const balance = ref<MediaSelection['display_balance']>(null)
const displayFailure = ref('')
const workspace = useNativeWorkspace()
const client = createBundlePreviewClient((path, init) => fetch(path, init))
const capability = computed(() =>
  widget.node.comfyClass
    ? bundleCapabilities.get(widget.node.comfyClass)
    : undefined
)

const sourceText = computed(() => {
  void revision.value
  const node = widget.node
  if (!node.graph) return ''
  const slot = node.inputs.findIndex(
    (input) => input.name === capability.value?.preview?.input
  )
  if (slot < 0) return ''
  const source = node.getInputNode(slot)
  if (source?.comfyClass !== 'APF_DATA_REFERENCE') return ''
  const value = source.widgets?.find(
    (control) => control.name === 'reference'
  )?.value
  return typeof value === 'string' ? value : ''
})

const reference = computed(() => {
  if (!sourceText.value) return undefined
  try {
    const parsed = scienceReferenceSchema.safeParse(
      JSON.parse(sourceText.value)
    )
    return parsed.success ? parsed.data : undefined
  } catch {
    return undefined
  }
})
const total = computed(() =>
  reference.value?.kind === 'dataset_version'
    ? reference.value.members.length
    : reference.value
      ? 1
      : 0
)
const parameters = computed(() => {
  void revision.value
  const controls = widget.node.widgets ?? []
  if (!capability.value) return undefined
  return Object.fromEntries(
    capability.value.node.definition.parameters.map((parameter) => [
      parameter.name,
      controls.find((control) => control.name === parameter.name)?.value ??
        parameter.default
    ])
  )
})
const signature = computed(() =>
  JSON.stringify([
    sourceText.value,
    parameters.value,
    index.value,
    capability.value?.available,
    capability.value?.node.content_token,
    capability.value?.development_source?.fingerprint,
    maxEdge.value,
    balance.value
  ])
)

const input = computed<{request?:BundleSampleRequest;error?:unknown}|undefined>(() => {
  if (
    !expanded.value ||
    !workspace.workspaceId.value ||
    !capability.value?.available ||
    !capability.value.operation ||
    !reference.value ||
    !parameters.value
  )
    return undefined
  try {
    const body = bundlePreviewRequestSchema
      .omit({ consumer_id: true, generation: true })
      .parse({
        reference: reference.value,
        member_index: index.value,
        parameters: parameters.value,
        package_id: capability.value.operation.package_id,
        operation_id: capability.value.operation.operation_id,
        preview_max_edge: maxEdge.value,
        display_balance: balance.value
      })
    return {request:{
      body,
      identity: signature.value,
      sourceKey: JSON.stringify([
        sourceText.value,
        index.value,
        body.package_id,
        body.operation_id
      ]),
      workspaceId: workspace.workspaceId.value
    }}
  } catch (cause) {
    return { error: cause }
  }
})
const preview = useBundleSamplePreview(
  computed(() => input.value?.request),
  client
)
const image = preview.image
const failure = computed(() => {
  if (displayFailure.value) return displayFailure.value
  if (expanded.value && capability.value && !capability.value.available)
    return capability.value.reason ?? t('apfSoftware.unavailable')
  const cause =
    workspace.error.value ??
    (input.value && 'error' in input.value ? input.value.error : undefined) ??
    preview.error.value
  return cause instanceof Error ? cause.message : cause ? String(cause) : ''
})
const notInstalled = computed(
  () =>
    Boolean(capability.value && !capability.value.available) ||
    (preview.error.value &&
      'code' in preview.error.value &&
      preview.error.value.code === 'SOFTWARE_NOT_READY')
)
const phase = computed(() =>
  failure.value
    ? 'failed'
    : !input.value
      ? 'idle'
      : preview.waiting.value
        ? 'waiting'
        : preview.updating.value
          ? 'updating'
          : image.value
            ? 'ready'
            : 'idle'
)
function render() {
  displayFailure.value = ''
  preview.retry()
}
function imageFailed() {
  displayFailure.value = t('astrophotoflow.previewUnavailable')
  preview.clearImage()
}
function changed() {
  revision.value++
}

watch(sourceText, () => {
  index.value = 0
})
watch([signature, expanded, workspace.workspaceId], () => {
  displayFailure.value = ''
})
onMounted(() => api.addEventListener('graphChanged', changed))
onBeforeUnmount(() => api.removeEventListener('graphChanged', changed))
</script>

<template>
  <div
    class="flex h-full min-w-0 flex-col gap-1 px-2 py-1"
    @pointerdown.stop
    @pointermove.stop
    @pointerup.stop
    @keydown.stop
    @wheel.stop
  >
    <Button
      size="sm"
      variant="textonly"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
      >{{ t('astrophotoflow.bundlePreview.quickPreview') }}</Button
    >
    <template v-if="expanded">
      <PreviewControls v-model:max-edge="maxEdge" v-model:balance="balance" />
      <div
        class="relative h-48 min-h-48 w-full overflow-hidden rounded-sm bg-component-node-widget-background"
      >
        <ImagePreview
          v-if="image"
          :image-urls="[image]"
          display-only
          :class="phase !== 'ready' ? 'opacity-40' : ''"
          @load-error="imageFailed"
        />
        <div
          v-if="phase !== 'ready'"
          class="absolute inset-0 flex flex-col items-center justify-center gap-2 overflow-auto p-2 text-center text-xs text-muted-foreground"
          :role="failure ? 'alert' : 'status'"
        >
          <i
            v-if="phase === 'waiting' || phase === 'updating'"
            class="icon-[lucide--loader-circle] size-4 animate-spin"
            aria-hidden="true"
          />
          <span class="max-h-24 overflow-auto wrap-break-word">{{
            failure ||
            t(
              phase === 'idle'
                ? 'astrophotoflow.bundlePreview.connectSource'
                : 'astrophotoflow.bundlePreview.updating'
            )
          }}</span>
          <Button
            v-if="notInstalled"
            size="sm"
            variant="secondary"
            @click="tabs.activeSidebarTabId = 'software'"
            >{{ t('apfSoftware.install') }}</Button
          >
          <Button
            v-if="phase === 'failed'"
            size="sm"
            variant="textonly"
            @click="render"
            >{{ t('g.retry') }}</Button
          >
        </div>
      </div>
      <div
        v-if="total > 1"
        class="flex h-7 items-center justify-between text-xs text-muted-foreground"
      >
        <Button
          size="icon"
          variant="textonly"
          :disabled="index === 0"
          :aria-label="t('g.previous')"
          @click="index--"
          ><i class="icon-[lucide--chevron-left] size-4"
        /></Button>
        <span>{{ index + 1 }} / {{ total }}</span>
        <Button
          size="icon"
          variant="textonly"
          :disabled="index + 1 >= total"
          :aria-label="t('g.next')"
          @click="index++"
          ><i class="icon-[lucide--chevron-right] size-4"
        /></Button>
      </div>
    </template>
  </div>
</template>
