<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import LibraryButton from '../components/LibraryButton.vue'
import { useObserveAssetContent, useAcceptAssetContent } from './mutations'
import { assetContentObservationSchema } from '../api/contracts'

const props=defineProps<{workspaceId:string;assetId:string;hasVersion:boolean}>()
const contentObservation=useObserveAssetContent()
const contentAcceptance=useAcceptAssetContent()
const emit=defineEmits<{accepted:[]}>()
const observation=ref<ReturnType<typeof assetContentObservationSchema.parse>>()
const busy=computed(()=>contentObservation.isPending.value||contentAcceptance.isPending.value)
const error=computed(()=>{const cause=contentObservation.error.value??contentAcceptance.error.value;return cause instanceof Error?cause.message:cause?uiT('apfUi.could_not_check_asset_content'):''})
const context=shallowRef({})
watch([()=>props.workspaceId,()=>props.assetId],()=>{
  context.value={};observation.value=undefined;contentObservation.reset();contentAcceptance.reset()
},{flush:'sync'})
onBeforeUnmount(()=>{context.value={}})

async function observe(){
  const request=context.value
  contentObservation.reset();contentAcceptance.reset();observation.value=undefined
  try{
    const result=await contentObservation.mutateAsync(props.assetId)
    if(request===context.value)observation.value=result
  }
  catch{/* The current mutation owns its error. */}
}

async function accept(){
  const current=observation.value
  if(!current||current.state!=='changed'||!current.observed_hash)return
  const assetId=props.assetId
  const request=context.value
  contentObservation.reset();contentAcceptance.reset()
  try{
    await contentAcceptance.mutateAsync({workspaceId:props.workspaceId,assetId,body:{
      base_version_id:current.base_version_id,base_revision:current.base_revision,expected_observed_hash:current.observed_hash
    }})
    if(request!==context.value)return
    observation.value=undefined
    emit('accepted')
  }catch{/* The current mutation owns its error. */}
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
