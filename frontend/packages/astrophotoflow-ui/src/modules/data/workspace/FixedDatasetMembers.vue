<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { assetApi } from '../api/index'
import PhotoPreviewDialog, { type PreviewPhoto } from './PhotoPreviewDialog.vue'

type FixedMember = { id: string; asset: { id: string; name: string }; version: { id: string } }
const props = defineProps<{ members: FixedMember[] }>()
const open = ref(false)
const page = ref(0)
const photo = ref<PreviewPhoto>()
const refreshError = ref('')
const urls = ref<Record<string, string>>({})
const visible = computed(() => props.members.slice(page.value * 10, page.value * 10 + 10))
let generation = 0
function clear() { for (const url of Object.values(urls.value)) URL.revokeObjectURL(url); urls.value = {} }
async function refreshThumbnail(photo: PreviewPhoto) {
  const current = generation
  refreshError.value = ''
  try {
    const blob = await assetApi.getBlob('/astrophotoflow/api/v1/library/assets/' + photo.assetId + '/versions/' + photo.versionId + '/previews/thumbnail')
    if (current !== generation) return
    for (const member of visible.value.filter(member => member.version.id === photo.versionId)) {
      if (urls.value[member.id]) URL.revokeObjectURL(urls.value[member.id]!)
      urls.value[member.id] = URL.createObjectURL(blob)
    }
  } catch (cause) { if (current === generation) refreshError.value = cause instanceof Error ? cause.message : '缩略图刷新失败。' }
}
watch([open, page, () => props.members], async () => {
  const current = ++generation
  clear()
  if (!open.value) return
  for (const member of visible.value) {
    try {
      const blob = await assetApi.getBlob('/astrophotoflow/api/v1/library/assets/' + member.asset.id + '/versions/' + member.version.id + '/previews/thumbnail')
      if (current !== generation) return
      urls.value[member.id] = URL.createObjectURL(blob)
    } catch { /* Unavailable thumbnails keep their named preview button. */ }
  }
})
onBeforeUnmount(() => { generation++; clear() })
</script>

<template>
  <div class="apf-fixed-members" @click.stop>
    <button type="button" :aria-expanded="open" @click="open=!open">查看固定版本 · {{ members.length }} 张</button>
    <section v-if="open" aria-label="固定版本照片">
      <p v-if="refreshError" role="alert">{{ refreshError }}</p>
      <ul><li v-for="member in visible" :key="member.id"><button type="button" :aria-label="'查看 ' + member.asset.name + ' 大图'" @click="photo={assetId:member.asset.id,versionId:member.version.id,title:member.asset.name}"><img v-if="urls[member.id]" :src="urls[member.id]" alt="" /><span>{{ member.asset.name }}</span></button></li></ul>
      <nav v-if="members.length>10" aria-label="固定版本照片分页"><button type="button" :disabled="page===0" @click="page--">上一页</button><span>{{ page+1 }} / {{ Math.ceil(members.length/10) }}</span><button type="button" :disabled="(page+1)*10>=members.length" @click="page++">下一页</button></nav>
    </section>
    <PhotoPreviewDialog :photo="photo" @close="photo=undefined" @updated="refreshThumbnail" />
  </div>
</template>

<style scoped>
.apf-fixed-members ul{list-style:none;padding:0;display:grid;gap:6px;max-height:440px;overflow:auto}
.apf-fixed-members li button{display:flex;align-items:center;gap:8px;text-align:left}
.apf-fixed-members img{width:100px;height:64px;object-fit:contain}
.apf-fixed-members nav{display:flex;align-items:center;gap:8px}
</style>
