<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePhotoPreview } from './usePhotoPreview'
import type { PreviewPhoto } from './previewTypes'
const props=defineProps<{workspaceId:string;photo?:PreviewPhoto}>()
const emit=defineEmits<{close:[];updated:[photo:PreviewPhoto]}>()
const {imageUrl,loading,error,retry:requestPreview}=usePhotoPreview(()=>props.workspaceId,()=>props.photo,value=>emit('updated',value))
const closeButton=ref<HTMLButtonElement>()
const imageFailure=ref('')
const displayError=()=>imageFailure.value||error.value
async function load(){imageFailure.value='';await requestPreview()}
function close(){emit('close')}
function escape(event:KeyboardEvent){
  if(props.photo&&event.key==='Escape'){event.preventDefault();event.stopPropagation();close()}
}
watch(()=>[props.workspaceId,props.photo] as const,async()=>{imageFailure.value='';await nextTick();closeButton.value?.focus()},{immediate:true})
onMounted(()=>window.addEventListener('keydown',escape,true))
onBeforeUnmount(()=>window.removeEventListener('keydown',escape,true))
</script>

<template>
  <div v-if="photo" class="apf-photo-backdrop" @click.self="close">
    <section class="apf-photo-dialog" role="dialog" aria-modal="true" :aria-label="photo.title + $t('apfUi.full_size_preview')">
      <header><strong>{{ photo.title }}</strong><button ref="closeButton" type="button" :aria-label="$t('apfUi.close_full_size_preview')" @click="close">{{ $t('apfUi.close') }}</button></header>
      <p v-if="loading" role="status">{{ $t('apfUi.reading_full_size_preview') }}</p>
      <div v-else-if="displayError()" class="apf-photo-error"><p role="alert">{{ displayError() }}</p><button type="button" @click="load()">{{ $t('apfUi.retry') }}</button></div>
      <div v-else-if="imageUrl" class="apf-photo-stage"><img :src="imageUrl" :alt="photo.title" @error="imageFailure=$t('apfUi.could_not_display_the_preview_please_try_again')" /></div>
    </section>
  </div>
</template>

<style scoped>
.apf-photo-backdrop{position:fixed;inset:0;z-index:1000;background:#000b;display:flex;align-items:center;justify-content:center;padding:20px}
.apf-photo-dialog{max-width:calc(100vw - 40px);max-height:calc(100vh - 40px);overflow:auto;min-width:280px;background:var(--comfy-menu-bg,#272727);color:var(--input-text,#ddd);border:1px solid var(--border-color,#555);border-radius:10px;box-shadow:0 12px 44px #0009;padding:12px}
.apf-photo-dialog header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:10px}
.apf-photo-dialog strong{overflow-wrap:anywhere}
.apf-photo-stage{background:#101010;border-radius:6px;overflow:hidden}
.apf-photo-stage img{display:block;max-width:min(1080px,calc(100vw - 66px));max-height:calc(100vh - 112px);width:auto;height:auto;object-fit:contain;margin:auto}
.apf-photo-dialog button{cursor:pointer;background:var(--comfy-input-bg,#333);color:inherit;border:1px solid var(--border-color,#555);border-radius:5px;padding:6px 12px;flex-shrink:0}
.apf-photo-error{max-width:600px;color:#ffb0b0}
</style>
