<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { z } from 'zod'
import { assetApi } from '../assets/host-client'
import {
  libraryTrashDeleteSchema, libraryTrashItemSchema, libraryTrashPreviewSchema,
  libraryTrashSelectionSchema, pageSchema
} from '../assets/contracts'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; changed: [] }>()
const rows = ref<z.infer<typeof libraryTrashItemSchema>[]>([])
const total = ref(0)
const offset = ref(0)
const selected = ref(new Set<string>())
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const preview = ref<z.infer<typeof libraryTrashPreviewSchema>>()
const deleteConfirm = ref(false)
const pageSize = 20
const expandedGroup = ref<string>()
const groupChildren = ref<z.infer<typeof libraryTrashItemSchema>[]>([])
const groupChildOffset = ref(0)
const groupChildTotal = ref(0)
const pageKeys = computed(() => rows.value.map(row => row.entry_type + ':' + row.id))
const displayRows = computed(() => {
  const ordered: typeof rows.value = [], used = new Set<string>()
  for (const group of rows.value.filter(row => row.entry_type === 'dataset')) {
    ordered.push(group); used.add(group.entry_type + ':' + group.id)
    for (const member of rows.value.filter(row => row.entry_type === 'asset' && group.member_asset_ids.includes(row.id))) {
      ordered.push(member); used.add(member.entry_type + ':' + member.id)
    }
  }
  for (const row of rows.value) if (!used.has(row.entry_type + ':' + row.id)) ordered.push(row)
  return ordered
})
const allSelected = computed(() => pageKeys.value.length > 0 && pageKeys.value.every(key => selected.value.has(key)))

function pageRequest(items: unknown[]) {
  return libraryTrashSelectionSchema.parse({items})
}
function selectionRows() {
  const selectedRows = new Map<string, z.infer<typeof libraryTrashItemSchema>>()
  for (const row of [...rows.value, ...groupChildren.value]) {
    const key = row.entry_type + ':' + row.id
    if (selected.value.has(key)) selectedRows.set(key, row)
  }
  return [...selectedRows.values()].map(row => ({
    entry_type: row.entry_type, id: row.id, removed_at: row.removed_at,
    revision: row.revision, current_version_id: row.current_version_id, source_dataset_id: row.source_dataset_id ?? null
  }))
}
async function load() {
  if (!props.open) return
  loading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams({limit:String(pageSize),offset:String(offset.value)})
    const result = await assetApi.get('/astrophotoflow/api/v1/library/trash?' + query, pageSchema(libraryTrashItemSchema))
    rows.value = result.items
    total.value = result.total
    selected.value = new Set()
    preview.value = undefined
    expandedGroup.value = undefined
    groupChildren.value = []
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '垃圾桶读取失败。' }
  finally { loading.value = false }
}
watch(() => props.open, open => { if (open) {offset.value=0;notice.value='';void load()} }, {immediate:true})
async function toggleGroup(group: z.infer<typeof libraryTrashItemSchema>) {
  if (expandedGroup.value === group.id) { expandedGroup.value = undefined; groupChildren.value = []; selected.value = new Set(); return }
  expandedGroup.value = group.id; groupChildOffset.value = 0
  await loadGroupChildren()
}
async function loadGroupChildren() {
  if (!expandedGroup.value) return
  loading.value = true; error.value = ''
  try {
    const query = new URLSearchParams({limit:String(pageSize),offset:String(groupChildOffset.value),group_id:expandedGroup.value})
    const result = await assetApi.get('/astrophotoflow/api/v1/library/trash?' + query, pageSchema(libraryTrashItemSchema))
    groupChildren.value = result.items; groupChildTotal.value = result.total
    selected.value = new Set()
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '组内照片读取失败。' }
  finally { loading.value = false }
}
function togglePage(event: Event) {
  const next = new Set(selected.value)
  for (const key of pageKeys.value) (event.target as HTMLInputElement).checked ? next.add(key) : next.delete(key)
  selected.value = next
}
function toggleRow(row: z.infer<typeof libraryTrashItemSchema>) {
  const next = new Set(selected.value), key = row.entry_type + ':' + row.id
  next.has(key) ? next.delete(key) : next.add(key)
  selected.value = next
}
async function restore() {
  if (!selected.value.size || busy.value) return
  busy.value = true; error.value=''; notice.value=''
  try {
    await assetApi.send('/astrophotoflow/api/v1/library/trash/restore', z.object({restored_count:z.number().int().nonnegative()}).strict(), 'POST', pageRequest(selectionRows()))
    notice.value='已恢复所选记录。'
    emit('changed')
    if (offset.value >= Math.max(0,total.value-selected.value.size)) offset.value=Math.max(0,offset.value-pageSize)
    await load()
  } catch(cause) { error.value=cause instanceof Error?cause.message:'恢复失败。' }
  finally {busy.value=false}
}
async function requestPreview() {
  if (!selected.value.size || busy.value) return
  busy.value=true;error.value='';preview.value=undefined
  try {
    preview.value=await assetApi.send('/astrophotoflow/api/v1/library/trash/delete-preview',libraryTrashPreviewSchema,'POST',pageRequest(selectionRows()))
    if (!preview.value.tasks.length) deleteConfirm.value=true
  } catch(cause) {error.value=cause instanceof Error?cause.message:'永久删除预览失败。'}
  finally {busy.value=false}
}
async function permanentlyDelete() {
  if (!preview.value || busy.value) return
  busy.value=true;error.value='';deleteConfirm.value=false
  try {
    const result=await assetApi.send('/astrophotoflow/api/v1/library/trash/delete',libraryTrashDeleteSchema,'POST',{
      ...pageRequest(selectionRows()),preview_fingerprint:preview.value.preview_fingerprint
    })
    notice.value=`已清理 ${result.deleted_count} 张照片、${result.deleted_entry_count} 条记录；删除文件 ${result.deleted_file_count} 个（${bytes(result.deleted_bytes)}），缺失文件 ${result.missing_file_count} 个。`+
      (result.failed.length?` ${result.failed.length} 项失败并保留在垃圾桶中。`:'')
    if (result.failed.length) error.value=result.failed.map(item=>`${item.id}：${item.error}`).join('；')
    emit('changed')
    await load()
  } catch(cause) {error.value=cause instanceof Error?cause.message:'永久删除失败。请重新预览后重试。'}
  finally {busy.value=false}
}
const bytes = (value:number) => value < 1024 ? `${value} B` : value < 1024*1024 ? `${(value/1024).toFixed(1)} KB` : `${(value/1024/1024).toFixed(1)} MB`
</script>

<template>
  <div v-if="open" class="trash-backdrop" role="presentation" @click.self="emit('close')">
    <section class="trash-dialog" role="dialog" aria-modal="true" aria-labelledby="trash-title">
      <header><h2 id="trash-title">垃圾桶</h2><button type="button" aria-label="关闭垃圾桶" @click="emit('close')">关闭</button></header>
      <p>恢复会撤销所选移除记录并保留原资产身份。永久删除无法在应用内恢复。</p>
      <p v-if="notice" role="status">{{notice}}</p><p v-if="error" class="trash-error" role="alert">{{error}}</p>
      <div class="trash-table-wrap">
        <table><thead><tr><th><input type="checkbox" aria-label="全选当前页" :checked="allSelected" :disabled="loading||busy" @change="togglePage"></th><th>名称</th><th>类型</th><th>移除时间</th><th>清理状态</th></tr></thead>
          <tbody><tr v-if="loading"><td colspan="5">正在读取垃圾桶…</td></tr><tr v-else-if="!rows.length"><td colspan="5">垃圾桶为空。</td></tr>
            <tr v-for="row in displayRows" :key="row.entry_type+':'+row.id" :class="{'trash-child-row':row.entry_type==='asset'&&rows.some(group=>group.entry_type==='dataset'&&group.member_asset_ids.includes(row.id))}"><td><input type="checkbox" :aria-label="'选择 '+row.name" :checked="selected.has(row.entry_type+':'+row.id)" :disabled="busy" @change="toggleRow(row)"></td><td><button v-if="row.entry_type==='dataset'" type="button" :aria-expanded="expandedGroup===row.id" @click="toggleGroup(row)">{{expandedGroup===row.id?'收起':'展开'}}</button>{{row.entry_type==='dataset'?'组 · ':''}}{{row.name}}<small v-if="row.entry_type==='dataset'">{{row.photo_count}} 张照片</small><small v-else-if="row.groups.length">归属组：{{row.groups.map(group=>group.name).join('、')}}</small><small v-if="row.cleanup_error" class="trash-error">{{row.cleanup_error}}</small></td><td>{{row.entry_type==='dataset'?'组':'照片'}}</td><td>{{new Date(row.removed_at).toLocaleString()}}</td><td>{{row.cleanup_status==='trash'?'待清理':row.cleanup_status==='partial'?'部分清理（不可恢复）':'清理失败'}}<span v-if="row.cleanup_status!=='trash'">：不可恢复</span></td></tr>
            <tr v-if="expandedGroup"><td colspan="5"><strong>组内待处理照片</strong></td></tr>
            <tr v-for="row in groupChildren" :key="'child:'+row.id" class="trash-child-row"><td><input type="checkbox" :aria-label="'选择 '+row.name" :checked="selected.has(row.entry_type+':'+row.id)" :disabled="busy" @change="toggleRow(row)"></td><td>{{row.name}}<small v-if="row.cleanup_error" class="trash-error">{{row.cleanup_error}}</small></td><td>照片</td><td>{{new Date(row.removed_at).toLocaleString()}}</td><td>{{row.cleanup_status==='trash'?'待清理':row.cleanup_status==='partial'?'部分清理（不可恢复）':'清理失败'}}</td></tr>
          </tbody>
        </table>
        <nav v-if="expandedGroup" class="trash-pages"><button type="button" :disabled="groupChildOffset===0||loading" @click="groupChildOffset=Math.max(0,groupChildOffset-pageSize);void loadGroupChildren()">组内上一页</button><span>{{groupChildTotal?groupChildOffset+1:0}}–{{Math.min(groupChildOffset+groupChildren.length,groupChildTotal)}} / {{groupChildTotal}}</span><button type="button" :disabled="groupChildOffset+groupChildren.length>=groupChildTotal||loading" @click="groupChildOffset+=pageSize;void loadGroupChildren()">组内下一页</button></nav>
      </div>
      <nav class="trash-pages" aria-label="垃圾桶分页"><button type="button" :disabled="offset===0||loading||busy" @click="offset=Math.max(0,offset-pageSize);void load()">上一页</button><span>{{total?offset+1:0}}–{{Math.min(offset+rows.length,total)}} / {{total}}</span><button type="button" :disabled="offset+rows.length>=total||loading||busy" @click="offset+=pageSize;void load()">下一页</button></nav>
      <footer><button type="button" :disabled="!selected.size||busy||selectionRows().some(row=>[...rows,...groupChildren].find(item=>item.id===row.id)?.cleanup_status!=='trash')" @click="restore">恢复</button><button type="button" :disabled="!selected.size||busy" @click="requestPreview">永久删除</button></footer>
      <section v-if="preview" class="trash-preview" aria-label="永久删除预览">
        <h3>删除范围</h3><p>照片 {{preview.photo_count}} 张；托管文件 {{preview.managed_file_count}} 个，共 {{bytes(preview.managed_bytes)}}。</p>
        <p v-if="preview.tasks.length" class="trash-error">导入任务仍占用：{{preview.tasks.join('、')}}。请先通过导入任务取消。</p>
        <div v-if="preview.references.length"><h4>将一并清理 {{preview.references.length}} 条项目或组关联</h4><p v-for="reference in preview.references" :key="reference.id">{{reference.name}} · {{reference.kind==='project_asset'?'项目照片':reference.kind==='project_dataset'?'项目数据集':'数据集成员'}} · 第 {{reference.version}} 版</p></div>
      </section>
      <div v-if="deleteConfirm" class="trash-confirm" role="alertdialog" aria-modal="true"><h3>确认永久删除</h3><p>将清理 {{preview?.items.length}} 条记录、{{preview?.photo_count}} 张照片、{{preview?.managed_file_count}} 个托管文件（{{bytes(preview?.managed_bytes??0)}}）及 {{preview?.references.length}} 条项目或组关联。此操作无法在应用内恢复。</p><p v-if="preview?.references.length">{{[...new Set(preview.references.map(reference=>reference.name))].join('、')}}</p><button type="button" :disabled="busy" @click="deleteConfirm=false">取消</button><button type="button" :disabled="busy" @click="permanentlyDelete">确认永久删除</button></div>
    </section>
  </div>
</template>

<style scoped>
.trash-backdrop{position:fixed;inset:0;z-index:1000;background:#0009;display:grid;place-items:center;padding:2rem}.trash-dialog{position:relative;background:var(--surface-card,#20232a);color:var(--text-color,#eee);border:1px solid #59616e;border-radius:.7rem;padding:1.2rem;max-width:900px;width:min(95vw,900px);max-height:90vh;overflow:auto}.trash-dialog header,.trash-dialog footer,.trash-pages{display:flex;align-items:center;justify-content:space-between;gap:.6rem}.trash-dialog h2{margin:.1rem 0}.trash-table-wrap{overflow:auto;max-height:38vh}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.5rem;border-bottom:1px solid #59616e}small{display:block;opacity:.8}.trash-error{color:#ff9b9b}.trash-preview,.trash-confirm{border:1px solid #788391;border-radius:.5rem;padding:.8rem;margin-top:.8rem}.trash-preview label{display:block;padding:.35rem}.trash-confirm{position:fixed;z-index:2;inset:50% auto auto 50%;transform:translate(-50%,-50%);width:min(88vw,540px);background:var(--surface-card,#20232a);box-shadow:0 10px 45px #000a}.trash-confirm button+button{margin-left:.5rem}.trash-child-row td:nth-child(2){padding-left:2rem}
</style>
