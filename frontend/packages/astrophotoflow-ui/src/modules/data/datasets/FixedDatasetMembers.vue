<script setup lang="ts">
import { uiT } from '../../../core/i18n'
import { computed, inject, ref, watch } from 'vue'
import { assetApi } from '../api'
import { fixedMemberAt } from './members'
import { useDatasetMembersQuery } from './queries'
import { useThumbnailUrls } from '../media/useThumbnailUrls'
import type { DatasetMemberPage } from '../../../generated/api/types.gen'
import PhotoPreviewDialog from '../media/PhotoPreviewDialog.vue'
import type { PreviewPhoto } from '../media/previewTypes'
import { libraryControlsKey } from '../workspace/libraryControls'
import type { MediaViewerRequest } from '../api/media'

const props = defineProps<{ workspaceId: string; datasetId: string; versionId: string | null; count: number }>()
const open=ref(false), page=ref(0)
const photo=ref<PreviewPhoto>()
const controls=inject(libraryControlsKey,undefined)
const mediaRequest=ref<MediaViewerRequest>()
const refreshError=ref('')
type Member=DatasetMemberPage['items'][number]
const query=useDatasetMembersQuery(()=>open.value&&props.versionId?{
  workspaceId:props.workspaceId,datasetId:props.datasetId,versionId:props.versionId,
  query:{limit:10,offset:page.value*10,sort_by:'position',order:'asc'},all:false
}:undefined,false)
const visible=computed(()=>query.data.value?.items??[])
const total=computed(()=>query.data.value?.total??props.count)
const loading=query.isFetching
const error=computed(()=>refreshError.value||(query.error.value instanceof Error?query.error.value.message:''))
function base(member: Member) {
  return member.version.view_base
}
const {urls,load:loadThumbnails,refresh:refreshMemberThumbnail,clear}=useThumbnailUrls<Member>(member=>member.id,(member,signal)=>assetApi.getBlob(base(member)+'/thumbnail',signal))
watch(()=>[props.workspaceId,props.datasetId,props.versionId] as const,()=>{
  page.value=0;photo.value=undefined;mediaRequest.value=undefined
},{flush:'sync'})
watch([open,page,()=>props.workspaceId,()=>props.datasetId,()=>props.versionId],()=>{
  clear();refreshError.value=''
},{flush:'sync'})
watch([query.dataUpdatedAt,visible],()=>{
  if(open.value&&props.versionId)void loadThumbnails(visible.value)
})
function openMember(member: Member) {
  if(!props.versionId)return
  if(!controls?.mediaViewer){photo.value={assetId:member.asset.id,versionId:member.version.id,title:member.asset.name,basePath:member.version.view_base};return}
  const reference={id:props.datasetId,versionId:props.versionId}
  mediaRequest.value={index:page.value*10+visible.value.findIndex(item=>item.id===member.id),total:total.value,
    member:async(index,signal)=>{const selected=await fixedMemberAt(reference,index,signal);return {title:selected.asset.name,basePath:base(selected)}}}
}
async function refreshThumbnail(updated: PreviewPhoto) {
  refreshError.value=''
  try {
    const aliases=visible.value.filter(member=>member.asset.id===updated.assetId&&member.version.id===updated.versionId)
    if(aliases[0])await refreshMemberThumbnail(aliases[0],aliases)
  }catch(cause){refreshError.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_refresh_the_thumbnail')}
}
</script>

<template>
  <div class="apf-fixed-members" @click.stop>
    <button type="button" :disabled="!versionId" :aria-expanded="open" @click="open=!open">{{ $t('apfUi.view_fixed_version_photos_value', { p0: count }) }}</button>
    <section v-if="open" :aria-label="$t('apfUi.fixed_version_photos')">
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loading" role="status">{{ $t('apfUi.reading_service_data') }}</p>
      <ul><li v-for="member in visible" :key="member.id"><button type="button" :aria-label="$t('apfUi.view') + member.asset.name + $t('apfUi.full_size')" @click="openMember(member)"><img v-if="urls[member.id]" :src="urls[member.id]" alt="" /><span>{{ member.asset.name }}</span></button></li></ul>
      <nav v-if="total>10" :aria-label="$t('apfUi.fixed_version_photo_pagination')"><button type="button" :disabled="page===0||loading" @click="page--">{{ $t('apfUi.previous_page') }}</button><span>{{ page+1 }} / {{ Math.ceil(total/10) }}</span><button type="button" :disabled="(page+1)*10>=total||loading" @click="page++">{{ $t('apfUi.next_page') }}</button></nav>
    </section>
    <PhotoPreviewDialog v-if="photo" :workspace-id="workspaceId" :photo="photo" @close="photo=undefined" @updated="refreshThumbnail" />
    <component :is="controls.mediaViewer" v-if="mediaRequest && controls?.mediaViewer" :request="mediaRequest" @close="mediaRequest=undefined" />
  </div>
</template>

<style scoped>
.apf-fixed-members ul{list-style:none;padding:0;display:grid;gap:6px;max-height:440px;overflow:auto}
.apf-fixed-members li button{display:flex;align-items:center;gap:8px;text-align:left}
.apf-fixed-members img{width:100px;height:64px;object-fit:contain}
.apf-fixed-members nav{display:flex;align-items:center;gap:8px}
</style>
