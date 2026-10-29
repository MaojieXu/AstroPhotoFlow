<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { z } from 'zod'
import { assetApi } from '../api/index'
import {
  libraryTrashDeleteSchema, libraryTrashItemSchema, libraryTrashPreviewSchema,
  libraryTrashSelectionSchema, pageSchema
} from '../api/contracts'

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
const previewSelection = ref<z.infer<typeof libraryTrashSelectionSchema>>()
const deleteConfirm = ref(false)
const pageSize = 20
const expandedGroup = ref<string>()
const groupChildren = ref<z.infer<typeof libraryTrashItemSchema>[]>([])
const groupChildOffset = ref(0)
const groupChildTotal = ref(0)
let readGeneration = 0
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
function clearPreview() {
  preview.value = undefined
  previewSelection.value = undefined
  deleteConfirm.value = false
}
function clearSelection() {
  selected.value = new Set()
  clearPreview()
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
  const generation = ++readGeneration
  clearSelection()
  rows.value = []
  expandedGroup.value = undefined
  groupChildren.value = []
  groupChildOffset.value = 0
  groupChildTotal.value = 0
  loading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams({limit:String(pageSize),offset:String(offset.value)})
    const result = await assetApi.get('/astrophotoflow/api/v1/library/trash?' + query, pageSchema(libraryTrashItemSchema))
    if (generation !== readGeneration || !props.open) return
    rows.value = result.items
    total.value = result.total
  } catch (cause) {
    if (generation === readGeneration && props.open) error.value = cause instanceof Error ? cause.message : '回收站读取失败。'
  } finally { if (generation === readGeneration && props.open) loading.value = false }
}
watch(() => props.open, open => {
  if (open) { offset.value=0; notice.value=''; void load() }
  else { readGeneration++; loading.value=false; expandedGroup.value=undefined; groupChildren.value=[]; groupChildTotal.value=0; clearSelection() }
}, {immediate:true})
async function toggleGroup(group: z.infer<typeof libraryTrashItemSchema>) {
  if (busy.value) return
  if (expandedGroup.value === group.id) {
    readGeneration++; loading.value=false; expandedGroup.value=undefined; groupChildren.value=[]; groupChildTotal.value=0; clearSelection(); return
  }
  expandedGroup.value = group.id; groupChildOffset.value = 0
  await loadGroupChildren()
}
async function loadGroupChildren() {
  if (!expandedGroup.value) return
  const generation = ++readGeneration
  const groupId = expandedGroup.value, childOffset = groupChildOffset.value
  clearSelection()
  groupChildren.value = []
  groupChildTotal.value = 0
  loading.value = true; error.value = ''
  try {
    const query = new URLSearchParams({limit:String(pageSize),offset:String(childOffset),group_id:groupId})
    const result = await assetApi.get('/astrophotoflow/api/v1/library/trash?' + query, pageSchema(libraryTrashItemSchema))
    if (generation !== readGeneration || !props.open || expandedGroup.value !== groupId || groupChildOffset.value !== childOffset) return
    groupChildren.value = result.items; groupChildTotal.value = result.total
  } catch (cause) {
    if (generation === readGeneration && props.open) error.value = cause instanceof Error ? cause.message : '组内照片读取失败。'
  } finally { if (generation === readGeneration && props.open) loading.value = false }
}
function togglePage(event: Event) {
  if (busy.value || loading.value) return
  clearPreview()
  const next = new Set(selected.value)
  for (const key of pageKeys.value) (event.target as HTMLInputElement).checked ? next.add(key) : next.delete(key)
  selected.value = next
}
function toggleRow(row: z.infer<typeof libraryTrashItemSchema>) {
  if (busy.value || loading.value) return
  clearPreview()
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
  const selection = pageRequest(selectionRows())
  const generation = readGeneration
  busy.value=true;error.value='';clearPreview()
  try {
    const result=await assetApi.send('/astrophotoflow/api/v1/library/trash/delete-preview',libraryTrashPreviewSchema,'POST',selection)
    if (generation !== readGeneration || !props.open) return
    preview.value=result
    previewSelection.value=selection
    if (!result.tasks.length&&!result.references.some(reference=>reference.kind==='calibration')) deleteConfirm.value=true
  } catch(cause) {if (generation === readGeneration && props.open) error.value=cause instanceof Error?cause.message:'永久删除预览失败。'}
  finally {busy.value=false}
}
async function permanentlyDelete() {
  if (!preview.value || !previewSelection.value || busy.value) return
  busy.value=true;error.value='';deleteConfirm.value=false
  try {
    const result=await assetApi.send('/astrophotoflow/api/v1/library/trash/delete',libraryTrashDeleteSchema,'POST',{
      ...previewSelection.value,preview_fingerprint:preview.value.preview_fingerprint
    })
    notice.value=`已清理 ${result.deleted_count} 张照片、${result.deleted_entry_count} 条记录；删除文件 ${result.deleted_file_count} 个（${bytes(result.deleted_bytes)}），缺失文件 ${result.missing_file_count} 个。`+
      (result.failed.length?` ${result.failed.length} 项保留在回收站中。${result.failed.map(item=>item.error).join('；')}`:'')
    if (result.failed.length) error.value=result.failed.map(item=>`${item.id}：${item.error}`).join('；')
    emit('changed')
    await load()
  } catch(cause) {clearPreview();error.value=cause instanceof Error?cause.message:'永久删除失败。请重新预览后重试。'}
  finally {busy.value=false}
}
const bytes = (value:number) => value < 1024 ? `${value} B` : value < 1024*1024 ? `${(value/1024).toFixed(1)} KB` : `${(value/1024/1024).toFixed(1)} MB`
</script>

<template>
  <div v-if="open" class="trash-backdrop" role="presentation" @click.self="!busy&&emit('close')">
    <section class="trash-dialog" role="dialog" aria-modal="true" aria-labelledby="trash-title">
      <header class="trash-header">
        <h2 id="trash-title">回收站</h2>
        <button type="button" aria-label="关闭回收站" :disabled="busy" @click="emit('close')">关闭</button>
      </header>
      <div class="trash-content">
        <p class="trash-description">恢复会保留原资产身份与资料。永久删除无法在应用内恢复。</p>
        <p v-if="notice" role="status">{{notice}}</p>
        <p v-if="error" class="trash-error" role="alert">{{error}}</p>
        <div class="trash-table-wrap">
          <table>
            <thead><tr><th class="trash-select"><input type="checkbox" aria-label="全选当前页" :checked="allSelected" :disabled="loading||busy" @change="togglePage"></th><th>名称</th><th>类型</th><th>移除时间</th><th>清理状态</th></tr></thead>
            <tbody>
              <tr v-if="loading&&!expandedGroup"><td colspan="5" class="trash-empty">正在读取回收站…</td></tr>
              <tr v-else-if="!rows.length"><td colspan="5" class="trash-empty">回收站为空。</td></tr>
              <template v-for="row in displayRows" :key="row.entry_type+':'+row.id">
                <tr :class="{'trash-child-row':row.entry_type==='asset'&&rows.some(group=>group.entry_type==='dataset'&&group.member_asset_ids.includes(row.id))}">
                  <td class="trash-select"><input type="checkbox" :aria-label="'选择 '+row.name" :checked="selected.has(row.entry_type+':'+row.id)" :disabled="loading||busy" @change="toggleRow(row)"></td>
                  <td>
                    <div class="trash-name">
                      <button v-if="row.entry_type==='dataset'" type="button" class="trash-expand" :aria-expanded="expandedGroup===row.id" :disabled="busy" @click="toggleGroup(row)">{{expandedGroup===row.id?'收起':'展开'}}</button>
                      <span>{{row.name}}</span>
                    </div>
                    <small v-if="row.entry_type==='dataset'">{{row.photo_count}} 张照片</small>
                    <small v-else-if="row.groups.length">归属组：{{row.groups.map(group=>group.name).join('、')}}</small>
                    <small v-if="row.cleanup_error" class="trash-error">{{row.cleanup_error}}</small>
                  </td>
                  <td>{{row.entry_type==='dataset'?'组':'照片'}}</td>
                  <td class="trash-date">{{new Date(row.removed_at).toLocaleString()}}</td>
                  <td><span :class="{'trash-error':row.cleanup_status!=='trash'}">{{row.cleanup_status==='trash'?'待清理':row.cleanup_status==='partial'?'部分清理（不可恢复）':'清理失败（不可恢复）'}}</span></td>
                </tr>
                <template v-if="row.entry_type==='dataset'&&expandedGroup===row.id">
                  <tr v-if="loading"><td colspan="5" class="trash-empty">正在读取组内照片…</td></tr>
                  <tr v-for="child in groupChildren" :key="'child:'+child.id" class="trash-child-row">
                    <td class="trash-select"><input type="checkbox" :aria-label="'选择 '+child.name" :checked="selected.has(child.entry_type+':'+child.id)" :disabled="loading||busy" @change="toggleRow(child)"></td>
                    <td>{{child.name}}<small v-if="child.cleanup_error" class="trash-error">{{child.cleanup_error}}</small></td>
                    <td>照片</td><td class="trash-date">{{new Date(child.removed_at).toLocaleString()}}</td>
                    <td><span :class="{'trash-error':child.cleanup_status!=='trash'}">{{child.cleanup_status==='trash'?'待清理':child.cleanup_status==='partial'?'部分清理（不可恢复）':'清理失败（不可恢复）'}}</span></td>
                  </tr>
                  <tr><td colspan="5" class="trash-group-pages">
                    <nav class="trash-pages" aria-label="组内照片分页">
                      <button type="button" :disabled="groupChildOffset===0||loading||busy" @click="groupChildOffset=Math.max(0,groupChildOffset-pageSize);void loadGroupChildren()">组内上一页</button>
                      <span>{{groupChildTotal?groupChildOffset+1:0}}–{{Math.min(groupChildOffset+groupChildren.length,groupChildTotal)}} / {{groupChildTotal}}</span>
                      <button type="button" :disabled="groupChildOffset+groupChildren.length>=groupChildTotal||loading||busy" @click="groupChildOffset+=pageSize;void loadGroupChildren()">组内下一页</button>
                    </nav>
                  </td></tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
        <section v-if="preview" class="trash-preview" aria-label="永久删除预览">
          <h3>删除范围</h3><p>照片 {{preview.photo_count}} 张；托管文件 {{preview.managed_file_count}} 个，共 {{bytes(preview.managed_bytes)}}。</p>
          <p v-if="preview.tasks.length" class="trash-error">导入任务仍占用：{{preview.tasks.join('、')}}。请先通过导入任务取消。</p>
          <div v-if="preview.references.length"><h4>{{preview.references.some(reference=>reference.kind==='calibration')?'项目、组或校准关联':'将一并清理'}} {{preview.references.length}} 条项目或组关联</h4><p v-for="reference in preview.references" :key="reference.id">{{reference.name}} · {{reference.kind==='project_asset'?'项目照片':reference.kind==='project_dataset'?'项目图像组':reference.kind==='calibration'?'保留中的校准引用':'图像组成员'}} · 第 {{reference.version}} 版</p></div>
          <p v-if="preview.references.some(reference=>reference.kind==='calibration')" role="alert">其他组的历史版本仍使用此校准目标，已阻止清理。先清理引用组；系统不会自动清空关联。</p>
        </section>
      </div>
      <footer class="trash-footer">
        <nav class="trash-pages" aria-label="回收站分页">
          <button type="button" :disabled="offset===0||loading||busy" @click="offset=Math.max(0,offset-pageSize);void load()">上一页</button>
          <span>{{total?offset+1:0}}–{{Math.min(offset+rows.length,total)}} / {{total}}</span>
          <button type="button" :disabled="offset+rows.length>=total||loading||busy" @click="offset+=pageSize;void load()">下一页</button>
        </nav>
        <div class="trash-actions">
          <span class="trash-selection">已选 {{selected.size}} 项</span>
          <button type="button" :disabled="!selected.size||busy||selectionRows().some(row=>[...rows,...groupChildren].find(item=>item.id===row.id)?.cleanup_status!=='trash')" @click="restore">恢复</button>
          <button type="button" class="trash-danger" :disabled="!selected.size||busy" @click="requestPreview">永久删除</button>
        </div>
      </footer>
      <div v-if="deleteConfirm" class="trash-confirm" role="alertdialog" aria-modal="true">
        <h3>确认永久删除</h3><p>将清理 {{preview?.items.length}} 条记录、{{preview?.photo_count}} 张照片、{{preview?.managed_file_count}} 个托管文件（{{bytes(preview?.managed_bytes??0)}}）及 {{preview?.references.length}} 条项目或组关联。此操作无法在应用内恢复。</p>
        <p v-if="preview?.references.length">{{[...new Set(preview.references.map(reference=>reference.name))].join('、')}}</p>
        <div class="trash-actions">
          <button type="button" :disabled="busy" @click="deleteConfirm=false">取消</button>
          <button type="button" class="trash-danger" :disabled="busy" @click="permanentlyDelete">确认永久删除</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.trash-backdrop { position:fixed; inset:0; z-index:1000; display:grid; place-items:center; padding:24px; background:#0008; }
.trash-dialog { position:relative; display:flex; flex-direction:column; box-sizing:border-box; width:min(100%,960px); max-height:85vh; overflow:hidden; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-bg,#353535); color:var(--input-text,#ddd); font-family:inherit; font-size:13px; font-weight:400; line-height:1.5; box-shadow:0 8px 32px #0006; }
.trash-header,.trash-footer { display:flex; flex:none; align-items:center; justify-content:space-between; gap:12px; padding:12px 16px; }
.trash-header { border-bottom:1px solid var(--border-color,#4e4e4e); }
.trash-dialog h2 { margin:0; font-size:16px; font-weight:600; }
.trash-dialog h3,.trash-dialog h4 { margin:0 0 8px; font-size:13px; font-weight:600; }
.trash-dialog p { margin:0; }
.trash-content { display:flex; flex-direction:column; gap:12px; min-height:0; padding:16px; overflow:auto; }
.trash-description,.trash-selection,.trash-pages { color:var(--descrip-text,#999); font-size:12px; }
.trash-dialog button { display:inline-flex; flex:none; align-items:center; justify-content:center; box-sizing:border-box; min-height:30px; padding:4px 10px; border:1px solid var(--border-color,#4e4e4e); border-radius:6px; background:var(--comfy-input-bg,#222); color:var(--input-text,#ddd); font:inherit; white-space:nowrap; cursor:pointer; }
.trash-dialog button:hover:not(:disabled) { background:var(--comfy-menu-secondary-bg,#292929); }
.trash-dialog button:focus-visible { outline:2px solid var(--content-preview-border,#8aa8d8); outline-offset:2px; }
.trash-dialog button:disabled { opacity:.45; cursor:default; }
.trash-table-wrap { min-height:0; max-height:50vh; overflow:auto; border:1px solid var(--border-color,#4e4e4e); border-radius:6px; }
table { width:100%; min-width:620px; border-collapse:collapse; font:inherit; }
th,td { padding:10px 12px; border-bottom:1px solid var(--border-color,#4e4e4e); text-align:left; vertical-align:middle; }
th { position:sticky; top:0; z-index:1; background:var(--comfy-menu-secondary-bg,#292929); color:var(--descrip-text,#999); font-size:12px; font-weight:500; white-space:nowrap; }
tbody tr:last-child td { border-bottom:0; }
tbody tr:hover { background:var(--comfy-menu-secondary-bg,#292929); }
.trash-select { width:20px; padding-right:4px; text-align:center; }
.trash-dialog input[type=checkbox] { display:inline-block; width:15px; height:15px; margin:0; vertical-align:middle; accent-color:var(--content-preview-border,#8aa8d8); }
.trash-name { display:flex; align-items:center; gap:8px; overflow-wrap:anywhere; }
.trash-dialog button.trash-expand { min-height:24px; padding:2px 6px; background:transparent; color:var(--descrip-text,#999); font-size:11px; }
small { display:block; margin-top:3px; color:var(--descrip-text,#999); font-size:11px; }
.trash-date { white-space:nowrap; font-variant-numeric:tabular-nums; }
.trash-child-row td:nth-child(2) { padding-left:32px; }
.trash-empty { padding:24px 12px; color:var(--descrip-text,#999); text-align:center; }
.trash-group-pages { padding:8px 12px 8px 32px; background:var(--comfy-menu-secondary-bg,#292929); }
.trash-pages,.trash-actions { display:flex; align-items:center; gap:8px; }
.trash-pages span { white-space:nowrap; font-variant-numeric:tabular-nums; }
.trash-footer { flex-wrap:wrap; border-top:1px solid var(--border-color,#4e4e4e); }
.trash-actions { justify-content:flex-end; margin-left:auto; }
.trash-selection { margin-right:4px; white-space:nowrap; }
.trash-error,.trash-dialog button.trash-danger { color:var(--error-text,#ff9b9b); }
.trash-dialog button.trash-danger { background:transparent; }
.trash-preview { padding:12px; border:1px solid var(--border-color,#4e4e4e); border-radius:6px; background:var(--comfy-menu-secondary-bg,#292929); }
.trash-preview p+p { margin-top:8px; }
.trash-confirm { position:fixed; z-index:2; inset:50% auto auto 50%; transform:translate(-50%,-50%); box-sizing:border-box; width:min(calc(100vw - 48px),540px); max-height:80vh; overflow:auto; padding:16px; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-bg,#353535); box-shadow:0 8px 32px #0008; }
.trash-confirm p { margin-bottom:12px; }
</style>
