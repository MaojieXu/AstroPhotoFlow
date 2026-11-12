<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createDataExportClient,
  dataResultSchema,
  useDataResult,
  useMediaOverview,
  useMediaView
} from '@astrophotoflow/ui'
import type { MediaState, MediaViewerRequest } from '@astrophotoflow/ui'
import type { ComponentWidget } from '@/scripts/domWidget'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'
import { useApp } from '@/scripts/appInstance'
import { api } from '@/scripts/api'
import Button from '@/components/ui/button/Button.vue'
import Dialog from '@/components/ui/dialog/Dialog.vue'
import DialogContent from '@/components/ui/dialog/DialogContent.vue'
import DialogHeader from '@/components/ui/dialog/DialogHeader.vue'
import DialogTitle from '@/components/ui/dialog/DialogTitle.vue'
import DialogPortal from '@/components/ui/dialog/DialogPortal.vue'
import DialogOverlay from '@/components/ui/dialog/DialogOverlay.vue'
import { imageSummary } from '../media/imageSummary'
import { formatSize } from '@/utils/formatUtil'
import MediaViewer from '../media/MediaViewer.vue'
import DataExportDialog from './DataExportDialog.vue'
import { useNativeWorkspace } from '../useNativeWorkspace'

const props = defineProps<{
  widget: ComponentWidget<string | object>
  reference?: unknown
  bindings: Record<string, (string | number)[]>
  sourcePath?: string
}>()
const { t } = useI18n()
const label = (key: string) => t(`astrophotoflow.dataExport.${key}`)
const outputs = useNodeOutputStore()
const workspace = useNativeWorkspace()
const client = createDataExportClient((path, init) => fetch(path, init))
const currentRun = ref('')
const executionFailure = ref('')
const candidate = computed(() => {
  const entries = outputs.getNodeOutputs(props.widget.node)?.apf_data
  if (!Array.isArray(entries)) return undefined
  const parsed = dataResultSchema.safeParse(entries.at(-1))
  if (
    !parsed.success ||
    parsed.data.state !== 'completed' ||
    parsed.data.workflow_id !== useApp().rootGraph.id
  )
    return undefined
  if (currentRun.value && parsed.data.run_id !== currentRun.value)
    return undefined
  const actual = parsed.data.input_bindings
  if (
    JSON.stringify(Object.keys(actual).sort()) !==
    JSON.stringify(Object.keys(props.bindings).sort())
  )
    return undefined
  if (
    Object.keys(actual).some(
      (key) =>
        JSON.stringify(actual[key]?.map(String)) !==
        JSON.stringify(props.bindings[key]?.map(String))
    )
  )
    return undefined
  if (!Object.keys(actual).length) {
    try {
      if (
        JSON.stringify(JSON.parse(String(props.reference))) !==
        JSON.stringify(parsed.data.reference)
      )
        return undefined
    } catch {
      return undefined
    }
  }
  return parsed.data
})
const checked = useDataResult(
  computed(() =>
    workspace.workspaceId.value && candidate.value
      ? {
          workspaceId: workspace.workspaceId.value,
          client,
          source: candidate.value
        }
      : undefined
  )
)
const result = computed(() => {
  const current = candidate.value,
    actual = checked.data.value
  return workspace.workspaceId.value &&
    current &&
    actual?.state === 'completed' &&
    actual.run_id === current.run_id &&
    actual.execution_id === current.execution_id &&
    actual.workflow_id === current.workflow_id
    ? actual
    : undefined
})
const index = ref(0)
const member = computed(() => result.value?.members[index.value])
const parameterSummary = computed(() => {
  const metadata = member.value?.metadata
  const raw = metadata?.parameters ?? metadata?.observed_parameters
  const parameters =
    raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const temperature = parameters.sensor_temperature_c ?? parameters.sensor_temperature_setpoint_c
  return [
    [t('astrophotoflow.exposure'), parameters.exposure_seconds == null ? undefined : `${parameters.exposure_seconds} s`],
    ['Gain', parameters.gain],
    ['ISO', parameters.iso],
    ['Offset', parameters.offset],
    [
      t('astrophotoflow.temperature'),
      temperature == null ? undefined : `${temperature} °C`
    ]
  ].filter(([, value]) => value !== undefined && value !== null)
})
const viewerMedia = ref<MediaState>()
const mediaView = useMediaView(
  computed(() =>
    workspace.workspaceId.value && member.value
      ? {
          workspaceId: workspace.workspaceId.value,
          basePath: member.value.view_base,
          selection: member.value.selection
        }
      : undefined
  )
)
const media = mediaView.state
const overview = useMediaOverview(
  computed(() => {
    const state = viewerMedia.value ?? media.value
    return workspace.workspaceId.value &&
      state?.status === 'available' &&
      state.overview_url
      ? {
          workspaceId: workspace.workspaceId.value,
          viewKey: state.key,
          url: state.overview_url
        }
      : undefined
  })
)
const image = overview.imageUrl
const failure = computed(() => {
  const cause =
    workspace.error.value ??
    checked.error.value ??
    checked.data.value?.error ??
    mediaView.error.value ??
    overview.error.value
  if (cause) return cause instanceof Error ? cause.message : String(cause)
  return media.value && !['available', 'generating'].includes(media.value.status)
    ? label('unavailable') : ''
})
const loading = computed(
  () =>
    checked.isFetching.value ||
    mediaView.loading.value ||
    overview.loading.value
)
async function retryPreview() {
  await mediaView.retry()
  if (overview.error.value) await overview.retry()
}
const viewer = ref<MediaViewerRequest>()
const exportTarget = ref<'library' | 'local'>()
const details = ref(false)
const onStart = (event: CustomEvent<{ prompt_id: string }>) => {
  if (props.widget.node.graph !== useApp().graph) return
  currentRun.value = event.detail.prompt_id
  executionFailure.value = ''
}
const onFailure = (
  event: CustomEvent<{ prompt_id: string; exception_message?: string }>
) => {
  if (event.detail.prompt_id === currentRun.value)
    executionFailure.value =
      event.detail.exception_message || label('executionFailed')
}
api.addEventListener('execution_start', onStart)
api.addEventListener('execution_error', onFailure)

function openViewer() {
  const snapshot = result.value
  if (!snapshot) return
  viewer.value = {
    index: index.value,
    total: snapshot.members.length,
    member: async (position) => ({
      title: snapshot.members[position]!.name,
      basePath: snapshot.members[position]!.view_base,
      selection: snapshot.members[position]!.selection
    })
  }
}
function selectedView(state: MediaState) {
  viewerMedia.value = state
}
watch(
  workspace.workspaceId,
  () => {
    currentRun.value = ''
    executionFailure.value = ''
    viewer.value = undefined
    exportTarget.value = undefined
  },
  { flush: 'sync' }
)
watch(
  () => result.value?.execution_id,
  () => {
    index.value = 0
    viewer.value = undefined
    exportTarget.value = undefined
  }
)
watch(
  () => [result.value?.execution_id, index.value],
  () => {
    viewerMedia.value = undefined
  },
  { flush: 'sync' }
)
onBeforeUnmount(() => {
  api.removeEventListener('execution_start', onStart)
  api.removeEventListener('execution_error', onFailure)
})
</script>

<template>
  <div class="flex min-h-0 min-w-0 flex-col gap-2">
    <p v-if="Object.keys(bindings).length" class="m-0 text-xs text-muted-foreground">
      {{
        t('astrophotoflow.nodeUi.upstream')
      }}
    </p>
    <p v-if="!result" class="text-sm text-muted-foreground" role="status">
      {{
        executionFailure || failure || label(loading ? 'preparing' : 'runFirst')
      }}
    </p>
    <template v-else>
      <strong v-if="result.members.length > 1 || result.reference?.kind === 'dataset'" class="truncate text-sm" :title="member?.name">{{
        member?.name
      }}</strong>
      <Button variant="textonly" size="unset"
        class="relative max-h-[30rem] min-h-40 w-full shrink-0 overflow-hidden rounded-sm bg-component-node-widget-background"
        :style="{ aspectRatio: media?.width && media?.height ? `${media.width} / ${media.height}` : '4 / 3' }"
        :aria-label="label('view')"
        @click="openViewer"
      >
        <img v-if="image" :src="image" :alt="member?.name" class="size-full object-contain" />
        <span v-else class="block p-3 text-xs text-muted-foreground">{{
          loading ? label('preparing') : label('view')
        }}</span>
      </Button>
      <div v-if="failure" role="alert" class="flex items-center gap-1 text-error">
        <span>{{ failure }}</span>
        <Button variant="textonly" size="sm" @click="retryPreview">{{ t('astrophotoflow.retryPreview') }}</Button>
      </div>
      <div v-if="result.members.length > 1" class="flex items-center justify-between">
        <Button
          variant="textonly"
          size="icon"
          :disabled="index === 0"
          :aria-label="t('g.previousImage')"
          @click="index--"
          >‹</Button
        ><span>{{ index + 1 }} / {{ result.members.length }}</span
        ><Button
          variant="textonly"
          size="icon"
          :disabled="index + 1 >= result.members.length"
          :aria-label="t('g.nextImage')"
          @click="index++"
          >›</Button
        >
      </div>
      <p class="m-0 break-words text-xs text-muted-foreground">
        {{ imageSummary(member?.format, { ...member?.metadata, width: media?.width ?? member?.metadata?.width, height: media?.height ?? member?.metadata?.height }) }}
      </p>
      <dl
        v-if="parameterSummary.length"
        class="m-0 grid grid-cols-2 gap-x-2 text-xs"
      >
        <div
          v-for="[name, value] in parameterSummary"
          :key="String(name)"
          class="flex gap-1"
        >
          <dt class="text-muted-foreground">{{ name }}</dt>
          <dd class="m-0">{{ value }}</dd>
        </div>
      </dl>
      <div class="flex justify-end">
        <Button size="sm" variant="textonly" @click="details = true">{{ t('astrophotoflow.imageDetails') }}</Button>
      </div>
      <div class="flex flex-wrap gap-1">
        <Button
          size="sm"
          variant="secondary"
          @click="exportTarget = 'library'"
          >{{ label('saveLibrary') }}</Button
        ><Button
          size="sm"
          variant="secondary"
          @click="exportTarget = 'local'"
          >{{ label('saveLocal') }}</Button
        >
      </div>
      <DataExportDialog
        v-if="exportTarget"
        :key="result.execution_id + exportTarget"
        :result="result"
        :index="index"
        :target="exportTarget"
        :media="viewerMedia ?? media"
        @close="exportTarget = undefined"
      />
      <Dialog v-model:open="details">
        <DialogPortal><DialogOverlay />
        <DialogContent :aria-describedby="undefined">
          <DialogHeader><DialogTitle>{{ t('astrophotoflow.imageDetails') }}</DialogTitle></DialogHeader>
          <dl class="grid grid-cols-[auto_minmax(0,1fr)] gap-2 text-sm">
            <template v-if="sourcePath"><dt>{{ t('astrophotoflow.nodeUi.importedPath') }}</dt><dd class="m-0 break-all">{{ sourcePath }}</dd></template>
            <dt>{{ t('astrophotoflow.nodeUi.filename') }}</dt><dd class="m-0 break-all">{{ member?.name }}</dd>
            <dt>{{ t('astrophotoflow.results.fileSize') }}</dt><dd class="m-0">{{ formatSize(member?.byte_size) }}</dd>
            <dt>{{ t('astrophotoflow.results.contentHash') }}</dt><dd class="m-0 break-all">{{ member?.content_hash ?? '—' }}</dd>
            <template v-for="[name, value] in parameterSummary" :key="String(name)"><dt>{{ name }}</dt><dd class="m-0">{{ value }}</dd></template>
          </dl>
        </DialogContent>
        </DialogPortal>
      </Dialog>
    </template>
    <MediaViewer
      v-if="viewer"
      :request="viewer"
      @close="viewer = undefined"
      @index="index = $event"
      @selection="selectedView"
    />
  </div>
</template>
