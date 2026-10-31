<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, ref, watch } from 'vue'
import { z } from 'zod'
import { assetApi } from '../api/index'
import { pageSchema } from '../api/contracts'

const props = defineProps<{ open:boolean }>()
const emit = defineEmits<{close:[];changed:[]}>()
const entrySchema=z.object({entry_type:z.enum(['project','equipment','equipment_setup','capture_preset']),id:z.string(),name:z.string(),revision:z.number().int(),updated_at:z.string(),details:z.record(z.string(),z.unknown())}).strict()
const dependencySchema=z.object({entry_type:z.enum(['project','equipment','equipment_setup','capture_preset']),id:z.string(),kind:z.string(),name:z.string(),count:z.number().int(),blocks_delete:z.boolean(),references:z.array(z.string())}).strict()
const previewSchema=z.object({items:z.array(entrySchema),dependencies:z.array(dependencySchema),blocked:z.boolean(),preview_fingerprint:z.string()}).strict()
const selected=ref(new Map<string,z.infer<typeof entrySchema>>())
const rows=ref<z.infer<typeof entrySchema>[]>([])
const total=ref(0)
const offset=ref(0)
const query=ref('')
const loading=ref(false)
const busy=ref(false)
const error=ref('')
const notice=ref('')
const preview=ref<z.infer<typeof previewSchema>>()
const previewSelection=ref<{items:Array<{entry_type:'project'|'equipment'|'equipment_setup'|'capture_preset';id:string;revision:number}>}>()
const deleteConfirm=ref(false)
const limit=20
let generation=0
const allOnPage=computed(()=>rows.value.length>0&&rows.value.every(row=>selected.value.has(row.entry_type+':'+row.id)))
const partiallyOnPage=computed(()=>rows.value.some(row=>selected.value.has(row.entry_type+':'+row.id))&&!allOnPage.value)

function resetSelection(){selected.value=new Map();preview.value=undefined;previewSelection.value=undefined;deleteConfirm.value=false}
async function load(){
  if(!props.open)return
  const current=++generation
  loading.value=true;error.value='';resetSelection()
  try{
    const params=new URLSearchParams({limit:String(limit),offset:String(offset.value)})
    if(query.value.trim())params.set('q',query.value.trim())
    const result=await assetApi.get('/astrophotoflow/api/v1/settings/trash?'+params,pageSchema(entrySchema))
    if(current!==generation||!props.open)return
    rows.value=result.items;total.value=result.total
  }catch(cause){if(current===generation&&props.open)error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_read_trash')}
  finally{if(current===generation&&props.open)loading.value=false}
}
watch(()=>props.open,open=>{if(open){offset.value=0;notice.value='';void load()}else{generation++;loading.value=false;resetSelection()}},{immediate:true})
watch(query,()=>{offset.value=0;void load()})
function togglePage(event:Event){
  const next=new Map(selected.value),checked=(event.target as HTMLInputElement).checked
  for(const row of rows.value){const key=row.entry_type+':'+row.id;if(checked)next.set(key,row);else next.delete(key)}
  selected.value=next;preview.value=undefined;previewSelection.value=undefined;deleteConfirm.value=false
}
function toggle(row:z.infer<typeof entrySchema>){
  const next=new Map(selected.value),key=row.entry_type+':'+row.id
  if(next.has(key))next.delete(key);else next.set(key,row)
  selected.value=next;preview.value=undefined;previewSelection.value=undefined;deleteConfirm.value=false
}
function requestItems(){return {items:[...selected.value.values()].map(row=>({entry_type:row.entry_type,id:row.id,revision:row.revision}))}}
async function restore(){
  if(!selected.value.size||busy.value)return
  busy.value=true;error.value='';notice.value=''
  try{
    await assetApi.send('/astrophotoflow/api/v1/settings/trash/restore',z.object({restored_count:z.number().int()}).strict(),'POST',requestItems())
    emit('changed');notice.value=uiT('apfUi.selected_records_restored');await load()
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_restore')}
  finally{busy.value=false}
}
async function requestPreview(){
  if(!selected.value.size||busy.value)return
  const selection=requestItems()
  busy.value=true;error.value='';preview.value=undefined;previewSelection.value=undefined;deleteConfirm.value=false
  try{
    preview.value=await assetApi.send('/astrophotoflow/api/v1/settings/trash/delete-preview',previewSchema,'POST',selection)
    previewSelection.value=selection
    if(!preview.value.blocked)deleteConfirm.value=true
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_preview_permanent_deletion')}
  finally{busy.value=false}
}
async function permanentlyDelete(){
  if(!preview.value||!previewSelection.value||preview.value.blocked||busy.value)return
  busy.value=true;error.value='';deleteConfirm.value=false
  try{
    await assetApi.send('/astrophotoflow/api/v1/settings/trash/delete',z.object({deleted_count:z.number().int(),detached_material_count:z.number().int()}).strict(),'POST',{
      ...previewSelection.value,preview_fingerprint:preview.value.preview_fingerprint
    })
    emit('changed');notice.value=uiT('apfUi.selected_settings_permanently_deleted_asset_equipment_snapshots_are_re');await load()
  }catch(cause){preview.value=undefined;error.value=cause instanceof Error?cause.message:uiT('apfUi.permanent_deletion_failed_generate_a_new_preview_before_retrying_c9e640')}
  finally{busy.value=false}
}
function typeName(type:string){return type==='project'?uiT('apfUi.project'):type==='equipment'?uiT('apfUi.equipment'):type==='equipment_setup'?uiT('apfUi.use_setup'):uiT('apfUi.capture_preset')}
</script>

<template>
  <div v-if="open" class="settings-trash-backdrop" role="presentation" @click.self="!busy&&emit('close')">
    <section class="settings-trash" role="dialog" aria-modal="true" aria-labelledby="settings-trash-title">
      <header><h2 id="settings-trash-title">{{ $t('apfUi.trash_ba35dc') }}</h2><button type="button" :disabled="busy" @click="emit('close')">{{ $t('apfUi.close') }}</button></header>
      <p>{{ $t('apfUi.restore_settings_or_preview_permanent_deletion_assets_retain_their_equ') }}</p>
      <p v-if="notice" role="status">{{notice}}</p><p v-if="error" role="alert" class="settings-trash-error">{{error}}</p>
      <div class="settings-trash-tools"><input v-model="query" :placeholder="$t('apfUi.search_names')" :aria-label="$t('apfUi.search_trash')" :disabled="busy" />
        <button type="button" :disabled="busy||!selected.size" @click="restore">{{ $t('apfUi.restore') }}</button>
        <button type="button" class="settings-trash-danger" :disabled="busy||!selected.size" @click="requestPreview">{{ $t('apfUi.permanently_delete') }}</button>
      </div>
      <div class="settings-trash-table"><table><thead><tr><th><input type="checkbox" :aria-label="$t('apfUi.select_current_page')" :checked="allOnPage" :indeterminate="partiallyOnPage" :disabled="busy||!rows.length" @change="togglePage" /></th><th>{{ $t('apfUi.name') }}</th><th>{{ $t('apfUi.type') }}</th><th>{{ $t('apfUi.removed_at') }}</th></tr></thead>
        <tbody><tr v-for="row in rows" :key="row.entry_type+':'+row.id" :aria-selected="selected.has(row.entry_type+':'+row.id)" @click="toggle(row)">
          <td><input type="checkbox" :aria-label="$t('apfUi.select_beb481')+row.name" :checked="selected.has(row.entry_type+':'+row.id)" :disabled="busy" @click.stop @change="toggle(row)" /></td><td>{{row.name}}</td><td>{{typeName(row.entry_type)}}</td><td>{{new Date(row.updated_at).toLocaleString()}}</td>
        </tr><tr v-if="!loading&&!rows.length"><td colspan="4">{{ $t('apfUi.trash_is_empty') }}</td></tr></tbody>
      </table></div>
      <footer><button type="button" :disabled="busy||offset===0" @click="offset=Math.max(0,offset-limit);load()">{{ $t('apfUi.previous_page') }}</button><span>{{total?offset+1:0}}–{{Math.min(offset+limit,total)}} / {{total}}</span><button type="button" :disabled="busy||offset+limit>=total" @click="offset+=limit;load()">{{ $t('apfUi.next_page') }}</button></footer>
      <section v-if="preview" class="settings-trash-preview" :aria-label="$t('apfUi.permanent_deletion_preview')"><h3>{{ $t('apfUi.preview_deletion') }}</h3>
        <p>{{ $t('apfUi.selected_settings_value_deleting_equipment_retains_the_asset_equipment', { p0: (preview.items.length) }) }}</p>
        <ul><li v-for="dependency in preview.dependencies" :key="dependency.entry_type+dependency.id+dependency.kind">{{ $t('apfUi.value_value_items_value', { p0: (dependency.name), p1: (dependency.count), p2: (dependency.kind) }) }}<small v-if="dependency.references.length">（{{dependency.references.slice(0,8).join('、')}}<template v-if="dependency.references.length>8">{{ $t('apfUi.and_others_385a84') }}</template>）</small></li></ul>
        <p v-if="preview.blocked" role="alert">{{ $t('apfUi.some_settings_are_still_referenced_resolve_those_references_before_per') }}</p>
      </section>
      <div v-if="deleteConfirm" class="settings-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="settings-trash-confirm-title">
        <h3 id="settings-trash-confirm-title">{{ $t('apfUi.confirm_permanent_deletion') }}</h3><p>{{ $t('apfUi.this_cannot_be_undone_asset_equipment_snapshots_are_retained') }}</p>
        <button type="button" :disabled="busy" @click="deleteConfirm=false">{{ $t('apfUi.cancel') }}</button><button type="button" class="settings-trash-danger" :disabled="busy" @click="permanentlyDelete">{{ $t('apfUi.confirm_permanent_deletion') }}</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-trash-backdrop{position:fixed;inset:0;z-index:40;display:grid;place-items:center;padding:20px;background:#0009}.settings-trash{position:relative;width:min(920px,100%);max-height:90vh;overflow:auto;padding:16px;border:1px solid var(--border-color,#555);border-radius:9px;background:var(--comfy-menu-bg,#252525);color:var(--input-text,#ddd)}.settings-trash header,.settings-trash-tools,.settings-trash footer{display:flex;align-items:center;gap:8px}.settings-trash header h2{margin-right:auto}.settings-trash-tools{margin:12px 0}.settings-trash-tools input{flex:1;min-width:100px;height:32px;padding:0 9px;border:1px solid var(--border-color,#555);border-radius:7px;background:var(--comfy-input-bg,#222);color:inherit}.settings-trash-table{max-height:48vh;overflow:auto}.settings-trash table{width:100%;border-collapse:collapse}.settings-trash th,.settings-trash td{padding:8px;border-bottom:1px solid var(--border-color,#444);text-align:left}.settings-trash tbody tr{cursor:pointer}.settings-trash tbody tr[aria-selected=true]{background:var(--comfy-menu-secondary-bg,#333)}.settings-trash footer{justify-content:center;margin-top:12px}.settings-trash footer span{min-width:130px;text-align:center}.settings-trash-danger,.settings-trash-error{color:#ff9b9b}.settings-trash-preview{margin-top:12px;padding:10px;border:1px solid var(--border-color,#555);border-radius:7px}.settings-trash-confirm{position:fixed;inset:50% auto auto 50%;z-index:2;transform:translate(-50%,-50%);width:min(430px,calc(100vw - 36px));padding:16px;border:1px solid var(--border-color,#555);border-radius:8px;background:var(--comfy-menu-bg,#303030);box-shadow:0 8px 32px #0008}
</style>
