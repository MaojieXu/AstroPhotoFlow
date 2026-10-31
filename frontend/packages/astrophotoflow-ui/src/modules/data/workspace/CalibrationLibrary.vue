<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import {computed,inject,onBeforeUnmount,ref,watch} from 'vue'
import {assetApi} from '../api/index'
import {assetSchema,datasetSchema,pageSchema,type Asset} from '../api/contracts'
import type {WorkspaceContext} from './Workspace.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'
import LibraryInfo from './LibraryInfo.vue'
import LibraryButton from './LibraryButton.vue'
import { displayLabel } from './presentation'

const context=inject<WorkspaceContext>('workspace')!
let active=true
const creating=ref(false),loading=ref(false),saving=ref(false)
const photos=ref<Asset[]>([]),chosen=ref<string[]>([])
const name=ref(''),notes=ref(''),error=ref(''),frameType=ref('')
const visiblePhotos=computed(()=>photos.value.filter(photo=>!frameType.value||photo.classification?.frame_type===frameType.value))
watch(()=>Boolean(creating.value&&(name.value||notes.value||chosen.value.length)),value=>{context.calibrationDirty.value=value})
onBeforeUnmount(()=>{active=false;context.calibrationDirty.value=false})
async function begin(){
  creating.value=true;loading.value=true;error.value='';photos.value=[];chosen.value=[];name.value='';notes.value=''
  try{
    for(let offset=0;;offset+=200){
      const page=await assetApi.get('/astrophotoflow/api/v1/library/assets?role=calibration&limit=200&offset='+offset,pageSchema(assetSchema));photos.value.push(...page.items)
      if(offset+page.limit>=page.total)break
    }
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_read_calibration_photos')}finally{loading.value=false}
}
async function create(){
  saving.value=true;error.value=''
  try{
    const created=await assetApi.send('/astrophotoflow/api/v1/datasets',datasetSchema,'POST',{name:name.value,notes:notes.value||null,asset_version_ids:chosen.value})
    if(!active)return
    creating.value=false
    await context.loadRecords()
    if(!active)return
    const row=context.rows.value.find(row=>row.id===created.id)
    if(row)await context.openDataset(row)
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_create_the_calibration_group')}finally{saving.value=false}
}
</script>
<template>
  <section class="apf-calibration-library" :aria-label="$t('apfUi.independent_calibration_library')">
    <h2>{{ $t('apfUi.calibration_library') }}<LibraryInfo :label="$t('apfUi.calibration_library')" :text="$t('apfUi.bias_dark_flat_and_dark_flat_are_shown_separately_from_light_frames_ma')" /></h2>
    <LibraryButton type="button" :disabled="saving||context.loading.value" @click="begin">{{ $t('apfUi.create_a_group_from_existing_calibration_photos') }}</LibraryButton>
    <form v-if="creating" class="apf-editor" :aria-label="$t('apfUi.create_calibration_group')" @submit.prevent="create">
      <label>{{ $t('apfUi.calibration_group_name') }}<input v-model="name" required /></label><label>{{ $t('apfUi.description') }}<textarea v-model="notes" /></label>
      <label>{{ $t('apfUi.filter_by_frame_use_when_selecting') }}<select v-model="frameType"><option value="">{{ $t('apfUi.all_calibration_types') }}</option><option v-for="type in ['bias','dark','flat','dark_flat']" :key="type" :value="type">{{displayLabel(type)}}</option></select></label>
      <p>{{ $t('apfUi.explicitly_selected_versions_value_changing_the_frame_use_filter_retai', { p0: (chosen.length) }) }}</p>
      <p v-if="loading" role="status">{{ $t('apfUi.reading_imported_calibration_photos') }}</p>
      <div class="apf-calibration-photo-list"><label v-for="photo in visiblePhotos" :key="photo.id"><input v-if="photo.current_version_id" v-model="chosen" type="checkbox" :value="photo.current_version_id" />{{photo.name}} · {{displayLabel(photo.classification?.frame_type)}} · {{displayLabel(photo.classification?.frame_class)}} · v{{photo.current_version?.version_number}}</label></div>
      <LibraryButton type="button" :disabled="saving" @click="creating=false">{{ $t('apfUi.cancel') }}</LibraryButton><LibraryButton type="submit" variant="primary" :disabled="saving||loading||chosen.length===0">{{ $t('apfUi.create_logical_calibration_group') }}</LibraryButton>
    </form>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
    <WorkspaceRecords />
  </section>
</template>
<style scoped>
.apf-calibration-library>p,.apf-calibration-library>button{margin:10px}.apf-calibration-photo-list{max-height:280px;overflow:auto}.apf-calibration-photo-list label{display:flex;align-items:center;gap:8px;margin:8px 0}
</style>
