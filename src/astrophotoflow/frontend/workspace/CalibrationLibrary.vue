<script setup lang="ts">
import {computed,inject,onBeforeUnmount,ref,watch} from 'vue'
import {assetApi} from '../assets/host-client'
import {assetSchema,datasetSchema,pageSchema,type Asset} from '../assets/contracts'
import type {WorkspaceContext} from './Workspace.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'

const context=inject<WorkspaceContext>('workspace')!
const creating=ref(false),loading=ref(false),saving=ref(false)
const photos=ref<Asset[]>([]),chosen=ref<string[]>([])
const name=ref(''),notes=ref(''),error=ref(''),frameType=ref('')
const visiblePhotos=computed(()=>photos.value.filter(photo=>!frameType.value||photo.classification?.frame_type===frameType.value))
watch(()=>Boolean(creating.value&&(name.value||notes.value||chosen.value.length)),value=>{context.calibrationDirty.value=value})
onBeforeUnmount(()=>{context.calibrationDirty.value=false})
async function begin(){
  creating.value=true;loading.value=true;error.value='';photos.value=[];chosen.value=[];name.value='';notes.value=''
  try{
    for(let offset=0;;offset+=200){
      const page=await assetApi.get('/astrophotoflow/api/v1/library/assets?role=calibration&limit=200&offset='+offset,pageSchema(assetSchema));photos.value.push(...page.items)
      if(offset+page.limit>=page.total)break
    }
  }catch(cause){error.value=cause instanceof Error?cause.message:'校准照片读取失败。'}finally{loading.value=false}
}
async function create(){
  saving.value=true;error.value=''
  try{
    const created=await assetApi.send('/astrophotoflow/api/v1/datasets',datasetSchema,'POST',{name:name.value,notes:notes.value||null,asset_version_ids:chosen.value})
    creating.value=false
    await context.loadRecords()
    const row=context.rows.value.find(row=>row.id===created.id)
    if(row)await context.openDataset(row)
  }catch(cause){error.value=cause instanceof Error?cause.message:'校准组创建失败。'}finally{saving.value=false}
}
</script>
<template>
  <section class="apf-calibration-library" aria-label="独立校准素材库">
    <p>Bias、Dark、Flat、Dark Flat 与亮场分开展示；Master Light 仍属于亮场。已有混合组保留完整成员，可在“全部素材”继续查看未知用途。</p>
    <p>校准组按数据关系保存同一批原件的版本引用和场景说明，不复制照片，也不自动修改原分组。</p>
    <button type="button" :disabled="saving||context.loading.value" @click="begin">从已有校准照片创建组</button>
    <form v-if="creating" class="apf-editor" aria-label="创建校准组" @submit.prevent="create">
      <label>校准组名称<input v-model="name" required /></label><label>场景说明<textarea v-model="notes" /></label>
      <label>选择时按用途查看<select v-model="frameType"><option value="">全部校准用途</option><option v-for="type in ['bias','dark','flat','dark_flat']" :key="type" :value="type">{{type}}</option></select></label>
      <p>已明确选择 {{chosen.length}} 个版本；切换用途筛选保留已选版本。</p>
      <p v-if="loading" role="status">正在读取已导入校准照片…</p>
      <div class="apf-calibration-photo-list"><label v-for="photo in visiblePhotos" :key="photo.id"><input v-if="photo.current_version_id" v-model="chosen" type="checkbox" :value="photo.current_version_id" />{{photo.name}} · {{photo.classification?.frame_type}} · {{photo.classification?.frame_class}} · v{{photo.current_version?.version_number}}</label></div>
      <button type="button" :disabled="saving" @click="creating=false">取消</button><button type="submit" :disabled="saving||loading||chosen.length===0">创建逻辑校准组</button>
    </form>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
    <WorkspaceRecords />
  </section>
</template>
<style scoped>
.apf-calibration-library>p,.apf-calibration-library>button{margin:10px}.apf-calibration-photo-list{max-height:280px;overflow:auto}.apf-calibration-photo-list label{display:flex;align-items:center;gap:8px;margin:8px 0}
</style>
