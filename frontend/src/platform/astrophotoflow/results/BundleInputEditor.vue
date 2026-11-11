<script setup lang="ts">
import {
  BundleGeometryEditor,
  createCanvasDataClient,
  dataResultSchema,
  pixelSelectionSchema,
  scienceReferenceSchema,
  softwareCallResultSchema,
  useCanvasInspection
} from '@astrophotoflow/ui'
import type {
  MediaSelection,
  MediaState,
  MediaViewerRequest,
  NodeParameter
} from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { onGraphIntent } from '@/lib/litegraph/src/graphIntents'
import { useApp } from '@/scripts/appInstance'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'
import { isSelectOnly } from '@/utils/litegraphUtil'
import { createExecutableNodeMap } from '@/utils/executionUtil'
import {
  getExecutionIdByNode,
  getNodeByExecutionId
} from '@/utils/graphTraversalUtil'
import MediaImagePreview from '../media/MediaImagePreview.vue'
import MediaViewer from '../media/MediaViewer.vue'
import { useNativeWorkspace } from '../useNativeWorkspace'
import { automaticResultState } from './automatic'

type Point = [number, number]
const { node, parameter, input, revision, edge } = defineProps<{
  node: LGraphNode
  parameter: NodeParameter
  input?: string
  revision: number
  edge: number
}>()
const { t } = useI18n()
const workspace = useNativeWorkspace()
const outputs = useNodeOutputStore()
const app = useApp()
const client = createCanvasDataClient((path, init) => fetch(path, init))
const member = ref(0)
const frame = ref(0)
const media = ref<MediaState>()
const frames = ref(0)
const detail = ref<MediaViewerRequest>()
const focus = ref<Point>()
const graphRevision = ref(0)
onBeforeUnmount(onGraphIntent(event => {
  const graph = node.graph
  if (!graph) return
  if (event.type === 'set_widget') {
    const root = graph.rootGraph
    if (event.graphId === root.id || [...root.subgraphs.values()].some(subgraph => subgraph.id === event.graphId)) graphRevision.value++
  } else if ((event.type === 'connect' || event.type === 'disconnect') && event.graph.rootGraph === graph.rootGraph) {
    graphRevision.value++
  }
}))
const labels = computed(() => ({
  edit: t('astrophotoflow.bundle.editCoordinates'),
  remove: t('astrophotoflow.bundle.removePoint'),
  clear: t('astrophotoflow.bundle.clear'),
  second: t('astrophotoflow.bundle.secondPoint')
}))
const upstream = computed(() => {
  void revision
  void graphRevision.value
  const slot = node.inputs.findIndex((port) => port.name === input)
  if (slot < 0 || !node.isInputConnected(slot)) return
  const root = node.graph?.rootGraph
  if (!root) return
  const id = getExecutionIdByNode(root, node)
  const link = id
    ? createExecutableNodeMap(root).get(id)?.resolveInput(slot)
    : undefined
  if (!link || link.widgetInfo) return
  const source = getNodeByExecutionId(root, String(link.origin_id))
  if (source) return { source, port: link.origin_slot }
})
const materialReference = computed(() => {
  void revision
  void graphRevision.value
  const source = upstream.value?.source
  if (
    source?.comfyClass !== 'APF_DATA_REFERENCE' ||
    source.inputs.some((_, index) => source.isInputConnected(index))
  )
    return
  const raw = source.widgets?.find(
    (widget) => widget.name === 'reference'
  )?.value
  if (typeof raw !== 'string') return
  try {
    return scienceReferenceSchema.parse(JSON.parse(raw))
  } catch {
    return
  }
})
const inspection = useCanvasInspection(
  computed(() => {
    const workspaceId = workspace.workspaceId.value
    const reference = materialReference.value
    return workspaceId && reference
      ? { workspaceId, reference, memberIndex: member.value }
      : undefined
  }),
  client
)
const checkedPort = computed(() => {
  if (materialReference.value || !upstream.value) return
  const { source, port } = upstream.value
  const output = outputs.getNodeOutputs(source)
  const entries = output?.apf_result
  if (Array.isArray(entries)) {
    const result = softwareCallResultSchema.safeParse(entries.at(-1))
    const current = automaticResultState(source)?.signature
    if (
      result.success &&
      result.data.workflow_id === node.graph?.rootGraph.id &&
      result.data.state === 'completed' &&
      (!result.data.calculation_signature ||
        result.data.calculation_signature === current)
    )
      return result.data.ports[port]?.members
  }
  const data = output?.apf_data
  if (Array.isArray(data)) {
    const result = dataResultSchema.safeParse(data.at(-1))
    if (result.success && result.data.workflow_id === node.graph?.rootGraph.id)
      return result.data.members
  }
})
const total = computed(() => {
  const reference = materialReference.value
  if (reference?.kind === 'dataset') return inspection.data.value?.member_count ?? 0
  return reference ? 1 : (checkedPort.value?.length ?? 0)
})
const target = computed(() => {
  const reference = materialReference.value
  if (reference) {
    const inspected = inspection.data.value
    const selection = reference.selection
    if (
      inspected?.availability !== 'available' ||
      !inspected.content_hash ||
      !selection
    )
      return
    return {
      base: inspected.view_base,
      token: inspected.content_hash,
      hdu: selection.hdu_index,
      format: inspected.format,
      frames: 0
    }
  }
  const item = checkedPort.value?.[member.value]
  if (
    item &&
    'content_hash' in item &&
    typeof item.content_hash === 'string' &&
    item.content_hash
  ) {
    const token =
      'position_token' in item && typeof item.position_token === 'string'
        ? item.position_token
        : item.content_hash
    const hdu =
      'hdu_index' in item
        ? item.hdu_index
        : 'selection' in item
          ? mediaSelectionHdu(item.selection.hdu_index)
          : null
    return {
      base: item.view_base, token, hdu, format: item.format,
      frames: 'frame_count' in item && typeof item.frame_count === 'number' ? item.frame_count : 0
    }
  }
})
const frameTotal = computed(() => target.value?.frames || frames.value)
function mediaSelectionHdu(value: unknown) {
  return typeof value === 'number' ? value : null
}
const mediaSelection = computed<Partial<MediaSelection>>(() => ({
  hdu_index: target.value?.format === 'fits' && frameTotal.value > 1 ? undefined : target.value?.hdu ?? null,
  frame_index: frame.value,
  preview_max_edge: edge as MediaSelection['preview_max_edge']
}))
const rawValue = computed(() => {
  void revision
  void graphRevision.value
  const raw = node.widgets?.find(
    (widget) => widget.name === parameter.name
  )?.value
  if (typeof raw !== 'string' || !raw) return
  try {
    return JSON.parse(raw) as unknown
  } catch {
    return
  }
})
const selected = computed(() => {
  const parsed = pixelSelectionSchema.safeParse(rawValue.value)
  if (parsed.success) return parsed.data
})
const points = computed<Point[]>(() => {
  if (parameter.editor?.kind === 'curve') {
    const value = rawValue.value
    return Array.isArray(value)
      ? value.filter(
          (point): point is Point =>
            Array.isArray(point) &&
            point.length === 2 &&
            point.every(Number.isFinite)
        )
      : []
  }
  const value = selected.value
  return value &&
    value.source_token === target.value?.token &&
    value.member_index === member.value &&
    (value.frame_index ?? 0) === frame.value &&
    (value.hdu_index ?? null) === (media.value?.selection.hdu_index ?? null)
    ? value.points
    : []
})
watch(
  [() => upstream.value?.source, () => upstream.value?.port, () => JSON.stringify(materialReference.value)],
  () => {
    member.value = selected.value?.member_index ?? 0
    frame.value = selected.value?.frame_index ?? 0
  },
  { immediate: true }
)
watch(total, count => {
  if (count > 0 && member.value >= count) {
    member.value = 0
    frame.value = 0
  }
})
watch(() => target.value?.base, () => { frames.value = 0 })

function receivedMedia(state: MediaState) {
  media.value = state
  frames.value = state.frame_count ?? 0
}
watch(
  [() => target.value?.base, frame],
  () => {
    media.value = undefined
    focus.value = undefined
    detail.value = undefined
  }
)

function commit(points: Point[]) {
  const graph = node.graph
  const widget = node.widgets?.find((widget) => widget.name === parameter.name)
  const canvas = app.canvas
  if (
    !graph ||
    graph.rootGraph !== app.rootGraph ||
    !widget ||
    isSelectOnly(canvas)
  )
    return
  const state = media.value
  if (parameter.editor?.kind !== 'curve' && (!state || !target.value)) return
  const value =
    parameter.editor?.kind === 'curve'
      ? JSON.stringify(points)
      : points.length && state && target.value
        ? JSON.stringify(
            pixelSelectionSchema.parse({
              points,
              source_token: target.value.token,
              member_index: member.value,
              frame_index: state.frame_index ?? null,
              hdu_index: state.selection.hdu_index ?? null,
              width: state.width,
              height: state.height
            })
          )
        : ''
  const previous = widget.value
  if (value === previous) return
  canvas.emitBeforeChange()
  graph.beforeChange()
  try {
    widget.value = value
    widget.callback?.(value, canvas, node)
    node.onWidgetChanged?.(widget.name, value, previous, widget)
    graph.incrementVersion()
  } finally {
    graph.afterChange()
    canvas.emitAfterChange()
    canvas.setDirty(true, true)
  }
}

function inspect() {
  const current = target.value
  const state = media.value
  if (!current || !state || !focus.value) return
  detail.value = {
    index: 0,
    total: 1,
    fixedDisplay: true,
    focus: focus.value,
    member: async () => ({
      title: t('astrophotoflow.bundle.inspectPixels'),
      basePath: current.base,
      selection: state.selection
    })
  }
}

function chooseMember(value: string) {
  member.value = Math.min(total.value - 1, Math.max(0, Number(value) - 1))
  frame.value = 0
}
</script>

<template>
  <div v-if="parameter.editor" class="flex flex-col gap-2">
    <BundleGeometryEditor
      v-if="parameter.editor.kind === 'curve'"
      kind="curve"
      :points="points"
      :width="1"
      :height="1"
      :labels="labels"
      @edit="commit"
    />
    <template v-else-if="target">
      <div
        v-if="total > 1 || frameTotal > 1"
        class="flex flex-wrap gap-2"
      >
        <label v-if="total > 1"
          >{{ t('astrophotoflow.bundle.member') }}
          <input
            type="number"
            min="1"
            :max="total"
            :value="member + 1"
            @change="chooseMember(($event.target as HTMLInputElement).value)"
          />
        </label>
        <label v-if="frameTotal > 1"
          >{{ t('astrophotoflow.bundle.frame') }}
          <input
            type="number"
            min="1"
            :max="frameTotal"
            :value="frame + 1"
            @change="
              frame = Math.min(
                frameTotal - 1,
                Math.max(
                  0,
                  Number(($event.target as HTMLInputElement).value) - 1
                )
              )
            "
          />
        </label>
      </div>
      <MediaImagePreview
        :base="target.base"
        :title="labels.edit"
        :selection="mediaSelection"
        @media="receivedMedia"
      >
        <template #image="{ image, state }">
          <BundleGeometryEditor
            :kind="parameter.editor.kind"
            :points="points"
            :image="image"
            :width="state.width"
            :height="state.height"
            :labels="labels"
            @edit="commit"
            @inspect="focus = $event"
          />
        </template>
      </MediaImagePreview>
      <button
        v-if="focus"
        type="button"
        class="self-end underline"
        @click="inspect"
      >
        {{ t('astrophotoflow.bundle.inspectPixels') }}
      </button>
      <MediaViewer
        v-if="detail"
        :request="detail"
        @close="detail = undefined"
      />
    </template>
    <p v-else role="status" class="m-0 text-muted-foreground">
      {{
        inspection.error.value?.message ??
        t('astrophotoflow.bundle.editorNeedsInput')
      }}
    </p>
  </div>
</template>
