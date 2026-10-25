<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { assetApi } from '../assets/host-client'
import { displayPreviewSchema } from '../assets/contracts'

export type PreviewPhoto = { assetId: string; versionId: string; title: string; basePath?: string }
const props = defineProps<{ photo?: PreviewPhoto }>()
const emit = defineEmits<{ close: [] }>()
const imageUrl = ref('')
const loading = ref(false)
const error = ref('')
const closeButton = ref<HTMLButtonElement>()
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined

function clear() {
  clearTimeout(timer)
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''
}
async function load() {
  const current = ++generation
  clear()
  if (!props.photo) return
  const photo = props.photo
  const base = photo.basePath ?? '/astrophotoflow/api/v1/library/assets/' + photo.assetId + '/versions/' + photo.versionId + '/previews'
  loading.value = true
  error.value = ''
  async function read(start: boolean) {
    try {
      const state = start
        ? await assetApi.send(base + '/display', displayPreviewSchema, 'POST', {})
        : await assetApi.get(base + '/display/status', displayPreviewSchema)
      if (current !== generation) return
      if (state.status === 'generating') {
        timer = setTimeout(() => void read(false), 500)
        return
      }
      if (state.status !== 'available') {
        error.value = state.error?.message ?? '大图预览尚未就绪，请重试。'
        loading.value = false
        return
      }
      const blob = await assetApi.getBlob(base + '/display')
      if (current !== generation) return
      imageUrl.value = URL.createObjectURL(blob)
      loading.value = false
    } catch (cause) {
      if (current !== generation) return
      error.value = cause instanceof Error ? cause.message : '无法读取大图预览。'
      loading.value = false
    }
  }
  void read(true)
  await nextTick()
  closeButton.value?.focus()
}
function escape(event: KeyboardEvent) {
  if (props.photo && event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    emit('close')
  }
}
watch(() => props.photo, () => void load(), { immediate: true })
onMounted(() => window.addEventListener('keydown', escape, true))
onBeforeUnmount(() => { generation++; clear(); window.removeEventListener('keydown', escape, true) })
</script>

<template>
  <div v-if="photo" class="apf-photo-backdrop" @click.self="emit('close')">
    <section class="apf-photo-dialog" role="dialog" aria-modal="true" :aria-label="photo.title + ' 大图预览'">
      <header><strong>{{ photo.title }}</strong><button ref="closeButton" type="button" aria-label="关闭大图预览" @click="emit('close')">关闭</button></header>
      <p v-if="loading" role="status">正在读取大图预览…</p>
      <div v-else-if="error" class="apf-photo-error"><p role="alert">{{ error }}</p><button type="button" @click="load">重试</button></div>
      <img v-else-if="imageUrl" :src="imageUrl" :alt="photo.title" @error="error='无法显示预览，请重试。'" />
    </section>
  </div>
</template>

<style scoped>
.apf-photo-backdrop{position:fixed;inset:0;z-index:1000;background:#000b;display:flex;align-items:center;justify-content:center;padding:20px}
.apf-photo-dialog{max-width:calc(100vw - 40px);max-height:calc(100vh - 40px);overflow:auto;min-width:280px;background:var(--comfy-menu-bg,#272727);color:var(--input-text,#ddd);border:1px solid var(--border-color,#555);border-radius:10px;box-shadow:0 12px 44px #0009;padding:12px}
.apf-photo-dialog header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:10px}
.apf-photo-dialog strong{overflow-wrap:anywhere}
.apf-photo-dialog img{display:block;max-width:min(1080px,calc(100vw - 66px));max-height:calc(100vh - 112px);width:auto;height:auto;object-fit:contain;margin:auto}
.apf-photo-dialog button{cursor:pointer;background:var(--comfy-input-bg,#333);color:inherit;border:1px solid var(--border-color,#555);border-radius:5px;padding:5px 10px}
.apf-photo-error{max-width:600px;color:#ffb0b0}
</style>
