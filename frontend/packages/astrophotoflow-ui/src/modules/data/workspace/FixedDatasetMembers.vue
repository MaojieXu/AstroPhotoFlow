<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { assetApi } from '../api/index'
import PhotoPreviewDialog, { type PreviewPhoto } from './PhotoPreviewDialog.vue'
import { libraryControlsKey } from './libraryControls'
import type { MediaViewerRequest } from '../api/media'
import { ApiClientError } from '../api/client'

type FixedMember = { id: string; asset: { id: string; name: string }; version: { id: string } }
const props = defineProps<{ members: FixedMember[] }>()
const open = ref(false)
const page = ref(0)
const photo = ref<PreviewPhoto>()
const controls = inject(libraryControlsKey, undefined)
const mediaRequest = ref<MediaViewerRequest>()
const refreshError = ref('')
const urls = ref<Record<string, string>>({})
const visible = computed(() => props.members.slice(page.value * 10, page.value * 10 + 10))
let generation = 0
function clear() { for (const url of Object.values(urls.value)) URL.revokeObjectURL(url); urls.value = {} }
function openMember(member: FixedMember) {
  if (!controls?.mediaViewer) {
    photo.value = { assetId: member.asset.id, versionId: member.version.id, title: member.asset.name }
    return
  }
  const members = props.members.map(item => ({ title: item.asset.name, basePath: `/astrophotoflow/api/v1/library/assets/${item.asset.id}/versions/${item.version.id}/previews` }))
  mediaRequest.value = {
    index: props.members.findIndex(item => item.id === member.id), total: members.length,
    member: async (position, signal) => {
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
      const selected = members[position]
      if (!selected) throw new ApiClientError(uiT('apfUi.fixed_member_is_out_of_range'), 'contract')
      return selected
    }
  }
}
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
  } catch (cause) { if (current === generation) refreshError.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_refresh_the_thumbnail') }
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
    <button type="button" :aria-expanded="open" @click="open=!open">{{ $t('apfUi.view_fixed_version_photos_value', { p0: (members.length) }) }}</button>
    <section v-if="open" :aria-label="$t('apfUi.fixed_version_photos')">
      <p v-if="refreshError" role="alert">{{ refreshError }}</p>
      <ul><li v-for="member in visible" :key="member.id"><button type="button" :aria-label="$t('apfUi.view') + member.asset.name + $t('apfUi.full_size')" @click="openMember(member)"><img v-if="urls[member.id]" :src="urls[member.id]" alt="" /><span>{{ member.asset.name }}</span></button></li></ul>
      <nav v-if="members.length>10" :aria-label="$t('apfUi.fixed_version_photo_pagination')"><button type="button" :disabled="page===0" @click="page--">{{ $t('apfUi.previous_page') }}</button><span>{{ page+1 }} / {{ Math.ceil(members.length/10) }}</span><button type="button" :disabled="(page+1)*10>=members.length" @click="page++">{{ $t('apfUi.next_page') }}</button></nav>
    </section>
    <component :is="controls.mediaViewer" v-if="controls?.mediaViewer && mediaRequest" :request="mediaRequest" @close="mediaRequest=undefined" />
    <PhotoPreviewDialog v-else :photo="photo" @close="photo=undefined" @updated="refreshThumbnail" />
  </div>
</template>

<style scoped>
.apf-fixed-members ul{list-style:none;padding:0;display:grid;gap:6px;max-height:440px;overflow:auto}
.apf-fixed-members li button{display:flex;align-items:center;gap:8px;text-align:left}
.apf-fixed-members img{width:100px;height:64px;object-fit:contain}
.apf-fixed-members nav{display:flex;align-items:center;gap:8px}
</style>
