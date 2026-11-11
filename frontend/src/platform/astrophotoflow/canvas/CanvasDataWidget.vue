<script setup lang="ts">
import {
  createCanvasDataClient,
  createImportClient,
  createMediaClient,
  useCanvasInspection,
  useCanvasPathImport,
  useMediaView,
  useMediaOverview,
  scienceReferenceSchema,
  dataResultSchema
} from '@astrophotoflow/ui'
import type { MediaSelection, MediaViewerRequest } from '@astrophotoflow/ui'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'
import Dialog from '@/components/ui/dialog/Dialog.vue'
import DialogContent from '@/components/ui/dialog/DialogContent.vue'
import DialogHeader from '@/components/ui/dialog/DialogHeader.vue'
import DialogOverlay from '@/components/ui/dialog/DialogOverlay.vue'
import DialogPortal from '@/components/ui/dialog/DialogPortal.vue'
import DialogTitle from '@/components/ui/dialog/DialogTitle.vue'
import type { ComponentWidget } from '@/scripts/domWidget'
import { api } from '@/scripts/api'
import { useApp } from '@/scripts/appInstance'
import MediaViewer from '../media/MediaViewer.vue'
import { useNativeWorkspace } from '../useNativeWorkspace'
import PreviewControls from '../media/PreviewControls.vue'
import DataRunWidget from '../results/DataRunWidget.vue'
import { useNodeWidgetSize } from './useNodeWidgetSize'
import { imageSummary } from '../media/imageSummary'
import { formatSize } from '@/utils/formatUtil'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'
import { createExecutableNodeMap } from '@/utils/executionUtil'
import { getExecutionIdByNode } from '@/utils/graphTraversalUtil'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const workspace = useNativeWorkspace()
const client = createCanvasDataClient((path, init) => fetch(path, init))
const mediaClient = createMediaClient((path, init) => fetch(path, init))
const importClient = createImportClient((path, init) => fetch(path, init))
const pathImport = useCanvasPathImport(
  workspace.workspaceId,
  importClient,
  client
)
const revision = ref(0)
const graphChanged = () => {
  revision.value++
}
api.addEventListener('graphChanged', graphChanged)
onBeforeUnmount(() => api.removeEventListener('graphChanged', graphChanged))
const referenceText = computed(() => {
  void revision.value
  return widget.node.widgets?.find((item) => item.name === 'reference')?.value
})
const nodeOutputs = useNodeOutputStore()
const bindings = computed(() => {
  void revision.value
  const result: Record<string, (string | number)[]> = {}
  if (
    !widget.node.inputs?.some(
      (input) =>
        ['science', 'images'].includes(input.name) && input.link != null
    )
  )
    return result
  const root = useApp().rootGraph
  const id = getExecutionIdByNode(root, widget.node)
  const dto = id ? createExecutableNodeMap(root).get(id) : undefined
  for (const [slot, input] of (dto?.inputs ?? []).entries()) {
    if (!['science', 'images'].includes(input.name)) continue
    const link = dto?.resolveInput(slot)
    if (link && !link.widgetInfo)
      result[input.name] = [link.origin_id, link.origin_slot]
  }
  return result
})
const connected = computed(() => Object.keys(bindings.value).length > 0)
const runtime = computed(() => {
  if (widget.node.comfyClass !== 'APF_DATA_REFERENCE') return false
  if (connected.value) return true
  const entries = nodeOutputs.getNodeOutputs(widget.node)?.apf_data
  if (!Array.isArray(entries)) return false
  const parsed = dataResultSchema.safeParse(entries.at(-1))
  try {
    return (
      parsed.success &&
      parsed.data.workflow_id === useApp().rootGraph.id &&
      JSON.stringify(parsed.data.reference) ===
        JSON.stringify(JSON.parse(String(referenceText.value)))
    )
  } catch {
    return false
  }
})
const index = ref(0)
const fileReference = computed(
  () =>
    widget.node.comfyClass === 'APF_FILE_REFERENCE' ||
    data.value?.format === 'other'
)
const maxEdge = ref<MediaSelection['preview_max_edge']>(1024)
const balance = ref<MediaSelection['display_balance']>(null)
const displayFailure = ref('')
const details = ref(false)
const mediaRequest = ref<MediaViewerRequest>()
const importPath = ref('')
const importedSource = ref<{ reference: string; path: string }>()
const sourcePath = computed(() => {
  const source = importedSource.value
  return source && source.reference === referenceText.value ? source.path : undefined
})
const manualPath = ref(false)
const selecting = ref(false)
let chooser: AbortController | undefined
onBeforeUnmount(() => chooser?.abort())
const content = ref<HTMLElement>()
useNodeWidgetSize(() => widget, content)
const importing = pathImport.busy
const canvasFailure = ref('')
const importFailure = computed(() => {
  const cause = canvasFailure.value || pathImport.error.value
  return cause instanceof Error ? cause.message : cause ? String(cause) : ''
})

async function importImage() {
  const node = widget.node
  const graph = node.graph
  const reference = node.widgets?.find((item) => item.name === 'reference')
  if (
    !graph ||
    !reference ||
    importing.value ||
    !workspace.workspaceId.value ||
    !importPath.value.trim()
  )
    return
  const workspaceId = workspace.workspaceId.value,
    original = reference.value,
    workflowId = useApp().rootGraph.id
  const originalTitle = node.title
  const selectedPath = importPath.value.trim()
  const defaultTitles = ['', node.constructor.title, data.value?.name, data.value?.title]
  canvasFailure.value = ''
  try {
    const prepared = await pathImport.start(selectedPath)
    if (!prepared) return
    if (
      node.graph !== graph ||
      useApp().rootGraph.id !== workflowId ||
      workspace.workspaceId.value !== workspaceId ||
      reference.value !== original ||
      connected.value
    ) {
      canvasFailure.value = t('astrophotoflow.canvasChanged')
      return
    }
    const canvas = useApp().canvas
    canvas.emitBeforeChange()
    graph.beforeChange()
    try {
      reference.value = JSON.stringify(prepared.reference)
      importedSource.value = { reference: String(reference.value), path: selectedPath }
      if (node.title === originalTitle && defaultTitles.includes(originalTitle)) node.title = prepared.title
      canvas.setDirty(true, true)
    } finally {
      graph.afterChange()
      canvas.emitAfterChange()
    }
    revision.value++
  } catch (cause) {
    canvasFailure.value = cause instanceof Error ? cause.message : String(cause)
  }
}

async function chooseImage() {
  if (selecting.value || importing.value || connected.value || !workspace.workspaceId.value) return
  const controller = new AbortController()
  chooser = controller
  selecting.value = true
  canvasFailure.value = ''
  const graph = widget.node.graph
  const node = widget.node
  const workspaceId = workspace.workspaceId.value
  const original = referenceText.value
  try {
    const selected = await importClient.select({ mode: 'files' }, controller.signal)
    if (controller.signal.aborted || selected.cancelled) return
    if (widget.node !== node || node.graph !== graph || workspace.workspaceId.value !== workspaceId || referenceText.value !== original || connected.value) {
      canvasFailure.value = t('astrophotoflow.canvasChanged')
      return
    }
    if (selected.files.length !== 1) {
      canvasFailure.value = t('astrophotoflow.nodeUi.selectOneFile')
      return
    }
    importPath.value = selected.files[0]!.path
    selecting.value = false
    await importImage()
  } catch (cause) {
    if (!controller.signal.aborted) canvasFailure.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    if (chooser === controller) {
      selecting.value = false
      chooser = undefined
    }
  }
}
const parsed = computed(() => {
  if (runtime.value) return undefined
  try {
    return {
      reference: scienceReferenceSchema.parse(
        JSON.parse(String(referenceText.value))
      )
    }
  } catch (cause) {
    return {
      error: referenceText.value
        ? cause
        : t('astrophotoflow.chooseLibraryImage')
    }
  }
})
const inspection = useCanvasInspection(
  computed(() =>
    workspace.workspaceId.value && parsed.value?.reference
      ? {
          workspaceId: workspace.workspaceId.value,
          reference: parsed.value.reference,
          memberIndex: index.value
        }
      : undefined
  ),
  client
)
const mediaView = useMediaView(
  computed(() => {
    const item = inspection.data.value,
      reference = parsed.value?.reference
    if (
      !workspace.workspaceId.value ||
      !item ||
      !reference ||
      item.format === 'other' ||
      item.availability !== 'available'
    )
      return
    const selection = reference.selection
    return {
      workspaceId: workspace.workspaceId.value,
      basePath: item.view_base,
      selection: {
        hdu_index: selection?.hdu_index,
        ...(item.format === 'video' ? { frame_index: 0 } : {}),
        preview_max_edge: maxEdge.value,
        display_balance: balance.value
      }
    }
  }),
  mediaClient
)
const thumbnail = useMediaOverview(
  computed(() => {
    const item = inspection.data.value
    return workspace.workspaceId.value &&
      item?.format !== 'other' &&
      item?.preview_status === 'available' &&
      item.preview_url
      ? {
          workspaceId: workspace.workspaceId.value,
          viewKey: item.asset_id + '-thumbnail',
          url: item.preview_url
        }
      : undefined
  }),
  mediaClient
)
const overview = useMediaOverview(
  computed(() => {
    const state = mediaView.state.value
    return workspace.workspaceId.value &&
      state?.status === 'available' &&
      !state.needs_selection &&
      state.overview_url
      ? {
          workspaceId: workspace.workspaceId.value,
          viewKey: state.key,
          url: state.overview_url
        }
      : undefined
  }),
  mediaClient
)
const image = computed(() =>
  displayFailure.value
    ? ''
    : overview.imageUrl.value || thumbnail.imageUrl.value
)
const phase = computed(() => mediaView.state.value?.phase)
const data = computed(() => {
  const item = inspection.data.value,
    state = mediaView.state.value
  return item && state?.status === 'available' && overview.imageUrl.value
    ? { ...item, width: state.width, height: state.height }
    : item
})
const failure = computed(() => {
  const cause =
    displayFailure.value ||
    workspace.error.value ||
    parsed.value?.error ||
    inspection.error.value ||
    mediaView.error.value ||
    overview.error.value ||
    (!mediaView.state.value && !mediaView.loading.value && thumbnail.error.value)
  if (cause) return cause instanceof Error ? cause.message : String(cause)
  const state = mediaView.state.value,
    item = inspection.data.value
  if (state?.needs_selection)
    return t('astrophotoflow.media.chooseArrayInViewer')
  if (state && !['generating', 'available'].includes(state.status))
    return t('astrophotoflow.previewUnavailable')
  if (
    item &&
    item.format !== 'other' &&
    item.availability !== 'available' &&
    item.preview_status !== 'available' &&
    item.preview_status !== 'pending'
  )
    return item.preview_error ?? t('astrophotoflow.previewUnavailable')
  return ''
})
const loading = computed(
  () =>
    inspection.isFetching.value ||
    mediaView.loading.value ||
    overview.loading.value ||
    (inspection.data.value?.preview_status === 'pending' &&
      inspection.data.value.availability !== 'available')
)
function text(value: unknown) {
  return value === null || value === undefined || value === ''
    ? t('astrophotoflow.unspecified')
    : String(value)
}

const summary = computed(() => {
  const item = data.value
  if (!item) return []
  if (fileReference.value)
    return [
      [
        t('astrophotoflow.results.fileSize'),
        item.byte_size == null ? text(null) : `${item.byte_size} B`
      ]
    ]
  const parameters = item.parameters
  const mode = parameters.parameter_mode
  return [
    [
      t('astrophotoflow.originalDimensions'),
      item.width !== null && item.height !== null
        ? `${item.width} × ${item.height}`
        : text(null)
    ],
    [
      t('astrophotoflow.exposure'),
      parameters.exposure_seconds == null
        ? text(null)
        : `${text(parameters.exposure_seconds)} s`
    ],
    [t('astrophotoflow.filter'), text(item.equipment.filter)],
    [
      mode === 'iso' ? 'ISO' : mode === 'gain' ? 'Gain' : 'ISO / Gain',
      text(
        mode === 'iso'
          ? parameters.iso
          : mode === 'gain'
            ? parameters.gain
            : null
      )
    ],
    [
      t('astrophotoflow.temperature'),
      parameters.sensor_temperature_c == null
        ? text(null)
        : `${text(parameters.sensor_temperature_c)} °C`
    ]
  ]
})

const extra = computed(() => {
  const item = data.value
  if (!item) return []
  if (fileReference.value)
    return [[t('astrophotoflow.results.contentHash'), text(item.content_hash)]]
  return [
    [t('astrophotoflow.nodeUi.filename'), text(item.name)],
    [t('astrophotoflow.results.fileSize'), formatSize(item.byte_size)],
    [t('astrophotoflow.results.contentHash'), text(item.content_hash)],
    [t('astrophotoflow.camera'), text(item.equipment.camera)],
    ['Offset', text(item.parameters.offset)],
    [
      'Bin X / Y',
      `${text(item.parameters.binning_x)} / ${text(item.parameters.binning_y)}`
    ],
    ['CFA', text(item.parameters.cfa_pattern)],
    [t('astrophotoflow.format'), text(item.format)],
    ['BITPIX', text(item.bitpix)],
    [t('astrophotoflow.pixelType'), text(item.pixel_type)]
  ]
})

function imageFailed() {
  displayFailure.value = t('astrophotoflow.previewUnavailable')
}
async function load() {
  displayFailure.value = ''
  await inspection.refetch()
  if (mediaView.state.value || mediaView.error.value) await mediaView.retry()
  await nextTick()
  if (overview.imageUrl.value) await overview.retry()
  if (thumbnail.imageUrl.value) await thumbnail.retry()
}

function openViewer() {
  if (fileReference.value) return
  let value: unknown
  try {
    value =
      typeof referenceText.value === 'string'
        ? JSON.parse(referenceText.value)
        : undefined
  } catch (cause) {
    displayFailure.value =
      cause instanceof Error ? cause.message : String(cause)
    return
  }
  const parsed = scienceReferenceSchema.safeParse(value)
  if (!parsed.success) return
  const reference = parsed.data
  mediaRequest.value = {
    index: index.value,
    total: inspection.data.value?.member_count ?? 1,
    member: async (position, signal) => {
      const client = createCanvasDataClient((path, init) =>
        fetch(path, { ...init, signal })
      )
      const current = await client.inspect(reference, position, signal)
      const selection = reference.selection
      return {
        title: current.name,
        basePath: current.view_base,
        selection: {
          hdu_index: selection?.hdu_index,
          preview_max_edge: maxEdge.value,
          display_balance: balance.value
        }
      }
    }
  }
}

watch(referenceText, () => {
  index.value = 0
  details.value = false
  mediaRequest.value = undefined
})
watch(
  [referenceText, index, runtime, maxEdge, balance, workspace.workspaceId],
  () => {
    displayFailure.value = ''
    mediaRequest.value = undefined
  },
  { flush: 'sync' }
)
</script>

<template>
  <div
    class="w-full min-w-0"
    @pointerdown.stop
    @pointermove.stop
    @pointerup.stop
    @keydown.stop
    @wheel.stop
  >
    <div ref="content" class="flex min-w-0 flex-col gap-2 px-2 py-1">
    <div v-if="!connected" class="flex items-center justify-between gap-1">
      <Button size="sm" variant="secondary" :disabled="selecting || importing || !workspace.workspaceId.value" @click="chooseImage">
        <i class="icon-[lucide--folder-open] mr-1 size-3.5" aria-hidden="true" />
        {{ t(selecting ? 'astrophotoflow.nodeUi.selecting' : importing ? 'astrophotoflow.importingImage' : referenceText ? 'astrophotoflow.nodeUi.replaceFile' : 'astrophotoflow.importImage') }}
      </Button>
      <Button variant="textonly" size="icon-sm" :aria-label="t('astrophotoflow.nodeUi.manualPath')" :title="t('astrophotoflow.nodeUi.manualPath')" :aria-expanded="manualPath" @click="manualPath = !manualPath">
        <i class="icon-[lucide--text-cursor-input] size-3.5" aria-hidden="true" />
      </Button>
    </div>
    <div v-if="!connected && manualPath" class="flex shrink-0 items-center gap-1">
      <Input
        v-model="importPath"
        class="min-w-0 flex-1"
        :aria-label="t('astrophotoflow.imagePath')"
        :placeholder="t('astrophotoflow.imagePath')"
        :disabled="selecting || importing || connected || !workspace.workspaceId.value"
        @keydown.enter.prevent="!connected && importImage()"
      />
      <Button
        size="sm"
        variant="secondary"
        :disabled="
          importing ||
          selecting ||
          connected ||
          !workspace.workspaceId.value ||
          !importPath.trim()
        "
        @click="importImage"
        >{{
          t(
            importing
              ? 'astrophotoflow.importingImage'
              : 'astrophotoflow.importImage'
          )
        }}</Button
      >
    </div>
    <span v-if="importFailure" role="alert" class="text-error">{{
      importFailure
    }}</span>
    <DataRunWidget
      v-if="runtime"
      :widget="widget"
      :reference="referenceText"
      :bindings="bindings"
      :source-path="connected ? undefined : sourcePath"
    />
    <template v-else-if="referenceText">
      <strong
        v-if="data && (data.member_count > 1 || parsed?.reference?.kind === 'dataset')"
        class="shrink-0 truncate text-base-foreground"
        :title="data?.name"
        >{{ data?.name ?? t('astrophotoflow.libraryImage') }}</strong
      >
      <div
        v-if="fileReference"
        class="flex min-h-20 items-center gap-2 rounded-sm bg-component-node-widget-background p-3"
      >
        <i class="icon-[lucide--file-text] size-6" aria-hidden="true" /><span
          class="wrap-break-word"
          >{{ failure || t('astrophotoflow.results.fixedFile') }}</span
        >
      </div>
      <details v-if="!fileReference" class="text-xs text-muted-foreground">
      <summary class="cursor-pointer">{{ t('astrophotoflow.nodeUi.displaySettings') }}</summary>
      <PreviewControls
        v-model:max-edge="maxEdge"
        v-model:balance="balance"
        :media="mediaView.state.value"
      />
      </details>
      <div
        v-if="!fileReference"
        class="group relative max-h-[30rem] min-h-40 w-full shrink-0 overflow-hidden rounded-sm bg-component-node-widget-background"
        :style="{ aspectRatio: data?.width && data?.height ? `${data.width} / ${data.height}` : '4 / 3' }"
        role="button"
        tabindex="0"
        :aria-label="t('astrophotoflow.media.open')"
        @click="openViewer"
        @keydown.enter.prevent="openViewer"
        @keydown.space.prevent="openViewer"
      >
        <img
          v-if="image"
          :src="image"
          :alt="data?.name ?? t('astrophotoflow.libraryImage')"
          class="size-full object-contain"
          @error="imageFailed"
        />
        <div
          v-else
          class="flex h-full min-w-0 flex-col items-center justify-center gap-2 px-3 text-muted-foreground"
          role="status"
        >
          <i
            :class="
              loading
                ? 'icon-[lucide--loader-circle] size-5 animate-spin'
                : 'icon-[lucide--image-off] size-5'
            "
            aria-hidden="true"
          />
          <span class="max-h-24 overflow-auto wrap-break-word">{{
            failure ||
            t(
              phase === 'queued'
                ? 'astrophotoflow.media.queued'
                : 'astrophotoflow.media.preparing'
            )
          }}</span>
          <Button v-if="failure" variant="textonly" @click.stop="load()">{{
            t('astrophotoflow.retryPreview')
          }}</Button>
        </div>
        <div
          v-if="image && (loading || failure)"
          class="absolute right-1 bottom-1 left-1 rounded-sm bg-base-background px-2 py-1"
          role="status"
        >
          {{
            failure ||
            t(
              phase === 'queued'
                ? 'astrophotoflow.media.queued'
                : 'astrophotoflow.media.preparing'
            )
          }}
          <Button v-if="failure" variant="textonly" @click.stop="load()">{{
            t('astrophotoflow.retryPreview')
          }}</Button>
        </div>
        <Button
          class="invisible absolute top-1 right-1 group-focus-within:visible group-hover:visible"
          variant="textonly"
          size="icon"
          :aria-label="t('astrophotoflow.media.open')"
          @click.stop="openViewer"
          ><i class="icon-[lucide--expand] size-4"
        /></Button>
      </div>
      <div v-if="data && data.member_count > 1" class="flex h-8 shrink-0 items-center justify-between gap-1">
        <Button
          size="icon"
          variant="textonly"
          :aria-label="t('g.previousImage')"
          :disabled="index === 0"
          @click="index--"
          ><i class="icon-[lucide--chevron-left] size-4"
        /></Button>
        <span class="text-muted-foreground">{{
          data ? `${index + 1} / ${data.member_count}` : t('g.loading')
        }}</span>
        <Button
          size="icon"
          variant="textonly"
          :aria-label="t('g.nextImage')"
          :disabled="!data || index + 1 >= data.member_count"
          @click="index++"
          ><i class="icon-[lucide--chevron-right] size-4"
        /></Button>
      </div>
      <p v-if="data" class="m-0 text-xs text-muted-foreground">{{ imageSummary(data.format, { width: data.width, height: data.height, pixel_type: data.pixel_type, bitpix: data.bitpix }) }}</p>
      <p v-if="data?.parameters.exposure_seconds != null" class="m-0 text-xs text-muted-foreground">{{ t('astrophotoflow.exposure') }} {{ data.parameters.exposure_seconds }} s</p>
      <div class="flex items-center justify-between gap-1">
        <span class="truncate text-muted-foreground" role="status">{{
          data?.availability === 'available'
            ? t('astrophotoflow.originalReady')
            : data
              ? t('astrophotoflow.originalUnavailable')
              : ''
        }}</span>
        <Button variant="textonly" :disabled="!data" @click="details = true">{{
          t('astrophotoflow.imageDetails')
        }}</Button>
      </div>
      <Dialog :open="details" @update:open="details = $event">
        <DialogPortal
          ><DialogOverlay /><DialogContent
            size="md"
            class="max-h-[85vh] overflow-y-auto"
            :aria-describedby="undefined"
          >
            <DialogHeader
              ><DialogTitle>{{ data?.name }}</DialogTitle
              ><Button
                variant="textonly"
                size="icon"
                :aria-label="t('g.close')"
                @click="details = false"
                ><i class="icon-[lucide--x] size-4" /></Button
            ></DialogHeader>
            <p class="text-muted-foreground">
              {{
                t(
                  fileReference
                    ? 'astrophotoflow.results.fixedFile'
                    : 'astrophotoflow.currentImageMetadata'
                )
              }}
            </p>
            <dl class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2">
              <template v-if="sourcePath"><dt>{{ t('astrophotoflow.nodeUi.importedPath') }}</dt><dd class="m-0 break-all">{{ sourcePath }}</dd></template>
              <template
                v-for="[label, value] in [...summary, ...extra]"
                :key="label"
                ><dt class="text-muted-foreground">{{ label }}</dt>
                <dd class="m-0 wrap-break-word">{{ value }}</dd></template
              >
            </dl>
          </DialogContent></DialogPortal
        >
      </Dialog>
      <MediaViewer
        v-if="mediaRequest"
        :request="mediaRequest"
        @close="mediaRequest = undefined"
        @index="index = $event"
      />
    </template>
    </div>
  </div>
</template>
