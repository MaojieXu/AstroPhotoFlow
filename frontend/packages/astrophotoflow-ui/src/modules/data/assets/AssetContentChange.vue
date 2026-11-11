<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import LibraryButton from '../components/LibraryButton.vue'
import { useObserveAssetContent } from './mutations'
import { assetContentObservationSchema } from '../api/contracts'

const props=defineProps<{workspaceId:string;assetId:string;hasOriginal:boolean}>()
const contentObservation=useObserveAssetContent()
const observation=ref<ReturnType<typeof assetContentObservationSchema.parse>>()
const busy=computed(()=>contentObservation.isPending.value)
const error=computed(()=>{const cause=contentObservation.error.value;return cause instanceof Error?cause.message:cause?uiT('apfUi.could_not_check_asset_content'):''})
const context=shallowRef({})
watch([()=>props.workspaceId,()=>props.assetId],()=>{
  context.value={};observation.value=undefined;contentObservation.reset()
},{flush:'sync'})
onBeforeUnmount(()=>{context.value={}})

async function observe(){
  const request=context.value
  contentObservation.reset();observation.value=undefined
  try{
    const result=await contentObservation.mutateAsync(props.assetId)
    if(request===context.value)observation.value=result
  }
  catch{/* The current mutation owns its error. */}
}

</script>

<template>
  <section class="apf-content-change" :aria-label="$t('apfUi.check_asset_file_changes')">
    <LibraryButton type="button" :disabled="busy||!hasOriginal" @click="observe">{{busy?$t('apfUi.processing'):$t('apfUi.check_file_changes')}}</LibraryButton>
    <p v-if="observation?.state==='unchanged'" role="status">{{ $t('apfUi.asset_original_unchanged') }}</p>
    <p v-else-if="observation?.state==='changed'" role="alert">{{ $t('apfUi.asset_original_changed_reimport') }}</p>
    <p v-else-if="observation?.state==='missing'" role="alert">{{ $t('apfUi.the_asset_file_is_currently_inaccessible_value', { p0: (observation.error?.message) }) }}</p>
    <p v-else-if="observation?.state==='unsupported'" role="alert">{{observation.error?.message}}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
  </section>
</template>

<style scoped>
.apf-content-change{display:grid;gap:6px;margin:10px 0}.apf-content-change p{margin:0}.apf-content-change>button{justify-self:start}
</style>
