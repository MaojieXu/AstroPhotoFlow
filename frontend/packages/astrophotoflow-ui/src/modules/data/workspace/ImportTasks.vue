<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ApiClientError } from '../api/client'
import { assetApi } from '../api/index'
import { pageSchema, taskActionSchema, taskSchema } from '../api/contracts'

const props = withDefaults(defineProps<{ refreshToken: number; uploadProgress?: Record<string, { loaded: number; total: number }>; watchTaskIds?: string[] }>(), {
  uploadProgress: () => ({}), watchTaskIds: () => []
})
const emit = defineEmits<{ completed: [taskId: string]; registered: [taskId: string] }>()
type Task = ReturnType<typeof taskSchema.parse>
defineSlots<{ default(props: { tasks: Task[]; resume: (task: Task) => Promise<void>; busyTaskId?: string; error: string }): unknown }>()
const tasks = ref<Task[]>([])
const error = ref('')
const busyTaskId = ref<string>()
let refreshTimer: ReturnType<typeof setInterval> | undefined
const notified = new Set<string>()
const registered = new Set<string>()
const visibleTasks = computed(() => tasks.value.filter(task => !(task.report as Record<string, any>).registration?.completed || ['interrupted', 'failed'].includes(task.status)))
const activeStatuses = ['queued', 'running', 'cancelling', 'interrupted']
const showError = computed(() => Boolean(error.value) && (props.refreshToken > 0 || tasks.value.length > 0))
const statusLabel = (status: string) => ({
  queued: '正在导入',
  running: '正在导入',
  cancelling: '正在停止',
  interrupted: '已暂停，进度已保存',
  failed: '导入失败'
}[status] ?? status)

function taskStatus(task: Task) {
  if ((task.report as Record<string, any>).upload_manifest && !(task.report as Record<string, any>).upload_complete) return '上传中'
  return statusLabel(task.status)
}

function taskProgress(task: Task) {
  const report = task.report as Record<string, any>
  const upload = props.uploadProgress[task.id]
  if (!report.upload_complete && upload) return upload.total ? Math.round(upload.loaded * 100 / upload.total) : 100
  if (!report.upload_complete && report.upload_manifest) {
    const total = report.upload_files.reduce((sum: number, file: { size: number }) => sum + file.size, 0)
    const loaded = report.upload_files.reduce((sum: number, file: { received: number }) => sum + file.received, 0)
    return total ? Math.round(loaded * 100 / total) : 0
  }
  if (!task.enumeration_completed) return undefined
  if (task.items_total === 0) return 0
  const registration = report.registration
  return registration ? (registration.total ? Math.round(registration.registered * 100 / registration.total) : 100) : Math.min(100, Math.round(task.items_completed * 100 / task.items_total))
}

function taskProgressText(task: Task) {
  const report = task.report as Record<string, any>
  const upload = props.uploadProgress[task.id]
  if (!report.upload_complete && upload) return Math.floor(upload.loaded / 1024 / 1024) + ' / ' + Math.ceil(upload.total / 1024 / 1024) + ' MB 已上传'
  if (report.upload_manifest && !report.upload_complete) return '等待文件上传'
  if (report.registration) return report.registration.registered + ' / ' + report.registration.total + ' 项已登记'
  return task.enumeration_completed
    ? task.items_completed + ' / ' + task.items_total + ' 项已处理'
    : task.items_completed + ' 项已处理，正在读取剩余来源'
}

function updateRefreshTimer() {
  const hasActive = tasks.value.some(task => activeStatuses.includes(task.status)) || props.watchTaskIds.length > 0
  if (hasActive && !refreshTimer) refreshTimer = setInterval(() => void loadTasks(), 1500)
  if (!hasActive && refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = undefined
  }
}

async function loadTasks() {
  error.value = ''
  try {
    const page = await assetApi.get(
      '/astrophotoflow/api/v1/asset-tasks?limit=50&offset=0&status=all',
      pageSchema(taskSchema)
    )
    const previous = new Map(tasks.value.map(task => [task.id, task.status]))
    for (const task of page.items) {
      if ((task.report as Record<string, any>).registration?.completed && (activeStatuses.includes(task.status) || props.watchTaskIds.includes(task.id)) && !registered.has(task.id)) {
        registered.add(task.id)
        emit('registered', task.id)
      }
      if (props.watchTaskIds.includes(task.id) && !activeStatuses.includes(task.status) && !notified.has(task.id)) {
        notified.add(task.id)
        emit('completed',task.id)
      }
    }
    tasks.value = page.items.filter(task => activeStatuses.includes(task.status) || task.status === 'failed')
    for(const task of page.items) if(previous.has(task.id) && activeStatuses.includes(previous.get(task.id) ?? '') && !activeStatuses.includes(task.status)) emit('completed',task.id)
    updateRefreshTimer()
  } catch (cause) {
    error.value = cause instanceof ApiClientError ? cause.message : '无法读取导入进度。'
  }
}

async function resume(task: Task) {
  busyTaskId.value = task.id
  error.value = ''
  try {
    await assetApi.send(
      '/astrophotoflow/api/v1/asset-tasks/' + task.id + '/resume',
      taskActionSchema,
      'POST',
      {}
    )
    await loadTasks()
  } catch (cause) {
    error.value = cause instanceof ApiClientError ? cause.message : '无法恢复导入。'
  } finally {
    busyTaskId.value = undefined
  }
}

watch([() => props.refreshToken, () => props.watchTaskIds], () => void loadTasks())
onMounted(() => void loadTasks())
onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <slot v-if="$slots.default" :tasks="visibleTasks" :resume="resume" :busy-task-id="busyTaskId" :error="error" />
  <section v-else-if="visibleTasks.length || showError" class="apf-import-progress" aria-label="导入进度">
    <article v-for="task in visibleTasks" :key="task.id" class="apf-import-progress__item">
      <div class="apf-import-progress__heading">
        <strong>{{ task.dataset_name || '素材导入' }}</strong>
        <span>{{ taskStatus(task) }}</span>
      </div>
      <progress
        :value="taskProgress(task)"
        max="100"
        :aria-label="taskProgressText(task)"
      />
      <div class="apf-import-progress__footer">
        <small>{{ task.status === 'failed' ? String(task.error?.message ?? '导入失败。') : taskProgressText(task) }}</small>
        <button
          v-if="task.status === 'interrupted'"
          type="button"
          :disabled="busyTaskId === task.id"
          @click="resume(task)"
        >{{ busyTaskId === task.id ? '恢复中…' : '继续导入' }}</button>
      </div>
    </article>
    <p v-if="showError" class="apf-error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.apf-import-progress{display:flex;flex-direction:column;gap:8px;margin:0 10px}
.apf-import-progress__item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 10px;padding:10px 12px;background:var(--comfy-menu-secondary-bg,#292929);border:1px solid var(--border-color,#4e4e4e);border-radius:8px}
.apf-import-progress__heading{display:flex;min-width:0;justify-content:space-between;gap:8px}
.apf-import-progress__heading strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.apf-import-progress__heading span{color:var(--descrip-text,#999);white-space:nowrap}
.apf-import-progress__item progress{grid-column:1/-1;width:100%;height:8px;accent-color:var(--content-preview-border,#8aa8d8)}
.apf-import-progress__heading,.apf-import-progress__footer,.apf-import-progress__item progress{opacity:1}
.apf-import-progress__heading,.apf-import-progress__footer{opacity:.58}
.apf-import-progress__footer{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:8px}
.apf-import-progress__footer small{color:var(--descrip-text,#999)}
.apf-error{grid-column:1/-1;color:#ffaaaa}
</style>
