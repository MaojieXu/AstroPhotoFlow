<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { onBeforeUnmount, ref, watch } from 'vue'
import LibraryButton from './LibraryButton.vue'
import { assetApi } from '../api/index'
import { assetContentObservationSchema, assetSchema } from '../api/contracts'

const props=defineProps<{assetId:string;hasVersion:boolean}>()
const emit=defineEmits<{accepted:[]}>()
const observation=ref<ReturnType<typeof assetContentObservationSchema.parse>>()
const error=ref('')
const busy=ref(false)
let generation=0
watch(()=>props.assetId,()=>{
  generation++;observation.value=undefined;error.value='';busy.value=false
},{flush:'sync'})
onBeforeUnmount(()=>{generation++})

async function observe(){
  const request=++generation
  busy.value=true;error.value='';observation.value=undefined
  try{
    const result=await assetApi.send(`/astrophotoflow/api/v1/library/assets/${props.assetId}/content-observation`,assetContentObservationSchema,'POST',undefined)
    if(request===generation)observation.value=result
  }
  catch(cause){if(request===generation)error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_check_asset_content')}
  finally{if(request===generation)busy.value=false}
}

async function accept(){
  const current=observation.value
  if(!current||current.state!=='changed'||!current.observed_hash)return
  const assetId=props.assetId
  const request=++generation
  busy.value=true;error.value=''
  try{
    await assetApi.send(`/astrophotoflow/api/v1/library/assets/${assetId}/content-accept`,assetSchema,'POST',{
      base_version_id:current.base_version_id,base_revision:current.base_revision,expected_observed_hash:current.observed_hash
    })
    if(request!==generation)return
    observation.value=undefined
    emit('accepted')
  }catch(cause){
    let queryError:unknown
    try{
      const latest=await assetApi.get(`/astrophotoflow/api/v1/library/assets/${assetId}`,assetSchema)
      if(request!==generation)return
      if(latest.current_version_id!==current.base_version_id&&latest.current_version?.content_hash===current.observed_hash){
        observation.value=undefined;emit('accepted');return
      }
    }catch(readCause){queryError=readCause}
    if(request!==generation)return
    const acceptMessage=cause instanceof Error?cause.message:uiT('apfUi.could_not_accept_the_new_asset_content')
    error.value=queryError instanceof Error?uiT('apfUi.value_could_not_verify_the_current_asset_value', { p0: (acceptMessage), p1: (queryError.message) }):acceptMessage
  }
  finally{if(request===generation)busy.value=false}
}
</script>

<template>
  <section class="apf-content-change" :aria-label="$t('apfUi.check_asset_file_changes')">
    <LibraryButton type="button" :disabled="busy||!hasVersion" @click="observe">{{busy?$t('apfUi.processing'):$t('apfUi.check_file_changes')}}</LibraryButton>
    <p v-if="observation?.state==='unchanged'" role="status">{{ $t('apfUi.file_content_matches_the_current_asset_version') }}</p>
    <div v-else-if="observation?.state==='changed'" role="status">
      <p>{{ $t('apfUi.the_file_content_has_changed_confirm_to_retain_the_asset_identity_and_') }}</p>
      <LibraryButton type="button" :disabled="busy" @click="accept">{{ $t('apfUi.confirm_new_content') }}</LibraryButton>
    </div>
    <p v-else-if="observation?.state==='missing'" role="alert">{{ $t('apfUi.the_asset_file_is_currently_inaccessible_value', { p0: (observation.error?.message) }) }}</p>
    <p v-else-if="observation?.state==='unsupported'" role="alert">{{observation.error?.message}}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
  </section>
</template>

<style scoped>
.apf-content-change{display:grid;gap:6px;margin:10px 0}.apf-content-change p{margin:0}.apf-content-change>button{justify-self:start}
</style>
