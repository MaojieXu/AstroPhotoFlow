<script setup lang="ts">
import { ref } from 'vue'
import { assetApi } from '../api/index'
import { assetContentObservationSchema, assetSchema } from '../api/contracts'

const props=defineProps<{assetId:string;hasVersion:boolean}>()
const emit=defineEmits<{accepted:[]}>()
const observation=ref<ReturnType<typeof assetContentObservationSchema.parse>>()
const error=ref('')
const busy=ref(false)

async function observe(){
  busy.value=true;error.value='';observation.value=undefined
  try{observation.value=await assetApi.send(`/astrophotoflow/api/v1/library/assets/${props.assetId}/content-observation`,assetContentObservationSchema,'POST',undefined)}
  catch(cause){error.value=cause instanceof Error?cause.message:'检查素材内容失败。'}
  finally{busy.value=false}
}

async function accept(){
  const current=observation.value
  if(!current||current.state!=='changed'||!current.observed_hash)return
  busy.value=true;error.value=''
  try{
    await assetApi.send(`/astrophotoflow/api/v1/library/assets/${props.assetId}/content-accept`,assetSchema,'POST',{
      base_version_id:current.base_version_id,base_revision:current.base_revision,expected_observed_hash:current.observed_hash
    })
    observation.value=undefined
    emit('accepted')
  }catch(cause){
    let queryError:unknown
    try{
      const latest=await assetApi.get(`/astrophotoflow/api/v1/library/assets/${props.assetId}`,assetSchema)
      if(latest.current_version_id!==current.base_version_id&&latest.current_version?.content_hash===current.observed_hash){
        observation.value=undefined;emit('accepted');return
      }
    }catch(readCause){queryError=readCause}
    const acceptMessage=cause instanceof Error?cause.message:'接纳新素材内容失败。'
    error.value=queryError instanceof Error?`${acceptMessage}；读取当前素材核对时失败：${queryError.message}`:acceptMessage
  }
  finally{busy.value=false}
}
</script>

<template>
  <section class="apf-content-change" aria-label="检查素材文件变化">
    <button type="button" :disabled="busy||!hasVersion" @click="observe">{{busy?'处理中…':'检查文件变化'}}</button>
    <p v-if="observation?.state==='unchanged'" role="status">文件内容与当前素材版本一致。</p>
    <div v-else-if="observation?.state==='changed'" role="status">
      <p>检测到文件内容已变化。确认后会保留素材身份并新增一个内容记录；已有固定引用不会自动切换。</p>
      <button type="button" :disabled="busy" @click="accept">确认使用新内容</button>
    </div>
    <p v-else-if="observation?.state==='missing'" role="alert">素材文件当前不可访问。{{observation.error?.message}}</p>
    <p v-else-if="observation?.state==='unsupported'" role="alert">{{observation.error?.message}}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
  </section>
</template>

<style scoped>
.apf-content-change{display:grid;gap:6px;margin:10px 0}.apf-content-change p{margin:0}
</style>
