<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ApiClientError } from '../assets/client'
import { assetApi } from '../assets/host-client'
import { assetSchema, datasetSchema, datasetVersionSchema, libraryEntriesRemoveRequestSchema, libraryEntriesRemoveSchema, pageSchema, type Asset } from '../assets/contracts'
import InlineField from './InlineField.vue'

const props=defineProps<{datasetId:string;pendingAssetVersionIds?:string[]}>()
const emit=defineEmits<{close:[];saved:[];updated:[];saving:[active:boolean];failure:[message:string]}>()
const dataset=ref<ReturnType<typeof datasetSchema.parse>>()
const members=ref<ReturnType<typeof datasetVersionSchema.parse>['members']>([])
const assets=ref<Asset[]>([])
const selection=ref<string[]>([])
const trashConfirmAsset=ref<Asset>()
const trashedAssetIds=ref(new Set<string>())
const busy=ref(false)
const error=ref('')
const inlineFailures=ref<Record<string,string>>({})
const errorMessage=computed(()=>Object.values(inlineFailures.value).at(-1)??error.value)
const existingIds=computed(()=>members.value.map(member=>member.asset_version_id))
function path(url:string,params:Record<string,string|number>={}){
  const query=new URLSearchParams(Object.entries(params).map(([k,v])=>[k,String(v)]))
  return '/astrophotoflow/api/v1'+url+'?'+query.toString()
}
function message(cause:unknown){return cause instanceof ApiClientError?cause.message:'请求失败。'}
function reportInlineFailure(){emit('failure',Object.values(inlineFailures.value).at(-1)??'')}
function setInlineFailure(key:string,message:string){inlineFailures.value={...inlineFailures.value,[key]:message};reportInlineFailure()}
function clearInlineFailure(key:string){
  if(!(key in inlineFailures.value))return
  const next={...inlineFailures.value}
  delete next[key]
  inlineFailures.value=next
  reportInlineFailure()
}
async function saveDatasetField(field:string,value:string|number|null){
  if(!dataset.value)return
  const failureKey='dataset:'+field
  busy.value=true;error.value='';clearInlineFailure(failureKey)
  let saved=false
  emit('saving',true)
  try{
    dataset.value=await assetApi.send('/astrophotoflow/api/v1/datasets/'+dataset.value.id,datasetSchema,'PATCH',{
      base_revision:dataset.value.revision,[field]:value===''?null:value
    })
    saved=true
  }catch(cause){const text=message(cause);setInlineFailure(failureKey,text);throw cause}
  finally{busy.value=false;emit('saving',false);if(saved)emit('updated')}
}
async function saveAssetField(asset:Asset,field:string,value:string|number|null){
  const classificationFields=['frame_class','frame_type']
  const parametersFields=['parameter_mode','iso','gain','offset','exposure_seconds','integration_seconds','sensor_temperature_c','binning_x','binning_y','camera_id','optical_system_id','filter_id']
  const body=classificationFields.includes(field)
    ? {base_revision:asset.revision,classification:{[field]:value}}
    : parametersFields.includes(field)
      ? {base_revision:asset.revision,parameters:{[field]:value===''?null:value}}
      : {base_revision:asset.revision,[field]:value===''?null:value}
  const failureKey='asset:'+asset.id+':'+field
  busy.value=true;error.value='';clearInlineFailure(failureKey);emit('saving',true)
  let saved=false
  try{
    const updated=await assetApi.send('/astrophotoflow/api/v1/library/assets/'+asset.id,assetSchema,'PATCH',body)
    assets.value=assets.value.map(item=>item.id===asset.id?updated:item)
    saved=true
  }catch(cause){const text=message(cause);setInlineFailure(failureKey,text);throw cause}
  finally{busy.value=false;emit('saving',false);if(saved)emit('updated')}
}
function close(){if(errorMessage.value&&!window.confirm('上次保存失败，仍要关闭并丢弃未保存输入吗？'))return;emit('close')}
async function load(){
  busy.value=true;error.value=''
  try{
    dataset.value=await assetApi.get('/astrophotoflow/api/v1/datasets/'+props.datasetId,datasetSchema)
    if(dataset.value.current_version_id){
      const version=await assetApi.get('/astrophotoflow/api/v1/datasets/'+props.datasetId+'/versions/'+dataset.value.current_version_id,datasetVersionSchema)
      members.value=version.members
      selection.value=version.members.map(member=>member.asset_version_id)
    }else{members.value=[];selection.value=[]}
    const found:Asset[]=[]
    for(let offset=0;;offset+=200){
      const page=await assetApi.get(path('/library/assets',{limit:200,offset,sort_by:'name',order:'asc',status:'all'}),pageSchema(assetSchema))
      found.push(...page.items)
      if(offset+page.limit>=page.total)break
    }
    assets.value=found
    for(const id of props.pendingAssetVersionIds??[]){
      const asset=assets.value.find(item=>item.current_version_id===id)
      if(asset&&!selection.value.includes(id))selection.value.push(id)
    }
  }catch(cause){error.value=message(cause)}
  finally{busy.value=false}
}
function orderedMembers(){
  const chosen=new Set(selection.value)
  const kept=existingIds.value.filter(id=>chosen.has(id))
  const added=assets.value.map(asset=>asset.current_version_id).filter((id):id is string=>!!id&&chosen.has(id)&&!existingIds.value.includes(id))
  return [...kept,...new Set(added)]
}
async function saveMembers(){
  if(!dataset.value)return
  const ids=orderedMembers()
  if(ids.length===existingIds.value.length&&ids.every((id,index)=>id===existingIds.value[index]))return
  busy.value=true;error.value=''
  try{
    await assetApi.send('/astrophotoflow/api/v1/datasets/'+dataset.value.id+'/versions',datasetVersionSchema,'POST',{
      base_revision:dataset.value.revision,asset_version_ids:ids
    })
    await load();emit('saved')
  }catch(cause){error.value=message(cause)}
  finally{busy.value=false}
}
async function moveMemberToTrash(){
  const asset=trashConfirmAsset.value
  if(!asset||busy.value)return
  busy.value=true;error.value=''
  try{
    await assetApi.send('/astrophotoflow/api/v1/library/items',libraryEntriesRemoveSchema,'DELETE',libraryEntriesRemoveRequestSchema.parse({items:[{
      entry_type:'asset',id:asset.id,revision:asset.revision,current_version_id:asset.current_version_id
    }]}))
    trashedAssetIds.value=new Set([...trashedAssetIds.value,asset.id])
    trashConfirmAsset.value=undefined
    emit('updated')
  }catch(cause){error.value=message(cause)}
  finally{busy.value=false}
}
onMounted(load)
</script>

<template>
  <section class="apf-editor apf-dataset-editor" aria-label="编辑数据集">
    <header><h2>数据集资料与成员</h2><button type="button" :disabled="busy" @click="close">关闭</button></header>
    <p v-if="busy" role="status">正在读取或保存…</p>
    <p v-if="errorMessage" class="apf-error" role="alert">{{errorMessage}}</p>
    <template v-if="dataset">
      <label>名称<InlineField :value="dataset.name" :save="value=>saveDatasetField('name',value)" @cancelled="clearInlineFailure('dataset:name')" /></label>
      <label>备注<InlineField :value="dataset.notes" kind="textarea" :save="value=>saveDatasetField('notes',value)" @cancelled="clearInlineFailure('dataset:notes')" /></label>
      <label>状态<InlineField :value="dataset.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveDatasetField('status',value)" @cancelled="clearInlineFailure('dataset:status')" /></label>
      <h3>固定成员（{{selection.length}}）</h3>
      <p>移除或添加成员会产生新数据集版本；已有成员顺序保留，新成员追加。</p>
      <div v-for="asset in assets" :key="asset.id" class="apf-dataset-choice">
      <label>
        <input v-model="selection" type="checkbox" :value="asset.current_version_id" :disabled="!asset.current_version_id" />
        <InlineField :value="asset.name" @click.stop :save="value=>saveAssetField(asset,'name',value)" @cancelled="clearInlineFailure('asset:'+asset.id+':name')" /> ·
        <InlineField v-if="asset.classification?.frame_class!=='video'" :value="asset.classification?.frame_type??''" :display="asset.classification?.frame_type??'未分类'" kind="select" @click.stop
          :choices="[{value:'',label:'未指定'},{value:'light',label:'light'},{value:'bias',label:'bias'},{value:'dark',label:'dark'},{value:'flat',label:'flat'},{value:'dark_flat',label:'dark_flat'}]"
          :save="value=>saveAssetField(asset,'frame_type',value)" @cancelled="clearInlineFailure('asset:'+asset.id+':frame_type')" />
        <span v-else>视频</span> · 曝光
        <InlineField :value="asset.parameters?.exposure_seconds as number|null|undefined" @click.stop kind="number" :save="value=>saveAssetField(asset,'exposure_seconds',value)" @cancelled="clearInlineFailure('asset:'+asset.id+':exposure_seconds')" />
        <InlineField :value="asset.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'已归档'}]" :save="value=>saveAssetField(asset,'status',value)" @click.stop @cancelled="clearInlineFailure('asset:'+asset.id+':status')" />
      </label>
      <button type="button" :disabled="busy||!asset.current_version_id||trashedAssetIds.has(asset.id)" @click="trashConfirmAsset=asset">{{trashedAssetIds.has(asset.id)?'已移入垃圾桶':'移入照片垃圾桶'}}</button>
      </div>
      <div class="apf-form-actions"><button type="button" :disabled="busy" @click="close">取消</button><button type="button" :disabled="busy||Boolean(errorMessage)" @click="saveMembers">保存成员版本</button></div>
    </template>
    <div v-if="trashConfirmAsset" class="apf-trash-confirm-backdrop" role="presentation" @click.self="trashConfirmAsset=undefined">
      <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="member-trash-title">
        <h3 id="member-trash-title">移入照片垃圾桶？</h3>
        <p>将移除“{{trashConfirmAsset.name}}”的正常展示。照片、版本和数据集成员关系保留，可从垃圾桶恢复。</p>
        <button type="button" :disabled="busy" @click="trashConfirmAsset=undefined">取消</button>
        <button type="button" :disabled="busy" @click="moveMemberToTrash">确认移入</button>
      </section>
    </div>
  </section>
</template>
