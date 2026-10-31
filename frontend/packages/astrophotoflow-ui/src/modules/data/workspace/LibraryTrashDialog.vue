<script setup lang="ts">
import { uiT } from '../../../core/i18n'

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
    if (generation === readGeneration && props.open) error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_read_trash')
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
    if (generation === readGeneration && props.open) error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_read_group_photos')
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
    notice.value=uiT('apfUi.selected_records_restored')
    emit('changed')
    if (offset.value >= Math.max(0,total.value-selected.value.size)) offset.value=Math.max(0,offset.value-pageSize)
    await load()
  } catch(cause) { error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_restore') }
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
  } catch(cause) {if (generation === readGeneration && props.open) error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_preview_permanent_deletion')}
  finally {busy.value=false}
}
async function permanentlyDelete() {
  if (!preview.value || !previewSelection.value || busy.value) return
  busy.value=true;error.value='';deleteConfirm.value=false
  try {
    const result=await assetApi.send('/astrophotoflow/api/v1/library/trash/delete',libraryTrashDeleteSchema,'POST',{
      ...previewSelection.value,preview_fingerprint:preview.value.preview_fingerprint
    })
    notice.value=uiT('apfUi.removed_value_photos_and_value_records_deleted_value_files_value_missi', { p0: (result.deleted_count), p1: (result.deleted_entry_count), p2: (result.deleted_file_count), p3: (bytes(result.deleted_bytes)), p4: (result.missing_file_count) })+
      (result.failed.length?uiT('apfUi.value_entries_remain_in_trash_value', { p0: (result.failed.length), p1: (result.failed.map(item=>item.error).join('；')) }):'')
    if (result.failed.length) error.value=result.failed.map(item=>`${item.id}：${item.error}`).join('；')
    emit('changed')
    await load()
  } catch(cause) {clearPreview();error.value=cause instanceof Error?cause.message:uiT('apfUi.permanent_deletion_failed_generate_a_new_preview_before_retrying')}
  finally {busy.value=false}
}
const bytes = (value:number) => value < 1024 ? `${value} B` : value < 1024*1024 ? `${(value/1024).toFixed(1)} KB` : `${(value/1024/1024).toFixed(1)} MB`
</script>

<template>
  <div v-if="open" class="trash-backdrop" role="presentation" @click.self="!busy&&emit('close')">
    <section class="trash-dialog" role="dialog" aria-modal="true" aria-labelledby="trash-title">
      <header class="trash-header">
        <h2 id="trash-title">{{ $t('apfUi.trash_ba35dc') }}</h2>
        <button type="button" :aria-label="$t('apfUi.close_trash')" :disabled="busy" @click="emit('close')">{{ $t('apfUi.close') }}</button>
      </header>
      <div class="trash-content">
        <p class="trash-description">{{ $t('apfUi.restoring_retains_the_original_asset_identity_and_metadata_permanent_d') }}</p>
        <p v-if="notice" role="status">{{notice}}</p>
        <p v-if="error" class="trash-error" role="alert">{{error}}</p>
        <div class="trash-table-wrap">
          <table>
            <thead><tr><th class="trash-select"><input type="checkbox" :aria-label="$t('apfUi.select_current_page')" :checked="allSelected" :disabled="loading||busy" @change="togglePage"></th><th>{{ $t('apfUi.name') }}</th><th>{{ $t('apfUi.type') }}</th><th>{{ $t('apfUi.removed_at') }}</th><th>{{ $t('apfUi.cleanup_status') }}</th></tr></thead>
            <tbody>
              <tr v-if="loading&&!expandedGroup"><td colspan="5" class="trash-empty">{{ $t('apfUi.reading_trash') }}</td></tr>
              <tr v-else-if="!rows.length"><td colspan="5" class="trash-empty">{{ $t('apfUi.trash_is_empty') }}</td></tr>
              <template v-for="row in displayRows" :key="row.entry_type+':'+row.id">
                <tr :class="{'trash-child-row':row.entry_type==='asset'&&rows.some(group=>group.entry_type==='dataset'&&group.member_asset_ids.includes(row.id))}">
                  <td class="trash-select"><input type="checkbox" :aria-label="$t('apfUi.select_beb481')+row.name" :checked="selected.has(row.entry_type+':'+row.id)" :disabled="loading||busy" @change="toggleRow(row)"></td>
                  <td>
                    <div class="trash-name">
                      <button v-if="row.entry_type==='dataset'" type="button" class="trash-expand" :aria-expanded="expandedGroup===row.id" :disabled="busy" @click="toggleGroup(row)">{{expandedGroup===row.id?$t('apfUi.collapse'):$t('apfUi.expand')}}</button>
                      <span>{{row.name}}</span>
                    </div>
                    <small v-if="row.entry_type==='dataset'">{{ $t('apfUi.photos_value', { p0: (row.photo_count) }) }}</small>
                    <small v-else-if="row.groups.length">{{ $t('apfUi.group_value', { p0: (row.groups.map(group=>group.name).join('、')) }) }}</small>
                    <small v-if="row.cleanup_error" class="trash-error">{{row.cleanup_error}}</small>
                  </td>
                  <td>{{row.entry_type==='dataset'?$t('apfUi.group'):$t('apfUi.photo')}}</td>
                  <td class="trash-date">{{new Date(row.removed_at).toLocaleString()}}</td>
                  <td><span :class="{'trash-error':row.cleanup_status!=='trash'}">{{row.cleanup_status==='trash'?$t('apfUi.pending_cleanup'):row.cleanup_status==='partial'?$t('apfUi.partial_cleanup_irreversible'):$t('apfUi.cleanup_failed_irreversible')}}</span></td>
                </tr>
                <template v-if="row.entry_type==='dataset'&&expandedGroup===row.id">
                  <tr v-if="loading"><td colspan="5" class="trash-empty">{{ $t('apfUi.reading_group_photos') }}</td></tr>
                  <tr v-for="child in groupChildren" :key="'child:'+child.id" class="trash-child-row">
                    <td class="trash-select"><input type="checkbox" :aria-label="$t('apfUi.select_beb481')+child.name" :checked="selected.has(child.entry_type+':'+child.id)" :disabled="loading||busy" @change="toggleRow(child)"></td>
                    <td>{{child.name}}<small v-if="child.cleanup_error" class="trash-error">{{child.cleanup_error}}</small></td>
                    <td>{{ $t('apfUi.photo') }}</td><td class="trash-date">{{new Date(child.removed_at).toLocaleString()}}</td>
                    <td><span :class="{'trash-error':child.cleanup_status!=='trash'}">{{child.cleanup_status==='trash'?$t('apfUi.pending_cleanup'):child.cleanup_status==='partial'?$t('apfUi.partial_cleanup_irreversible'):$t('apfUi.cleanup_failed_irreversible')}}</span></td>
                  </tr>
                  <tr><td colspan="5" class="trash-group-pages">
                    <nav class="trash-pages" :aria-label="$t('apfUi.group_photo_pagination')">
                      <button type="button" :disabled="groupChildOffset===0||loading||busy" @click="groupChildOffset=Math.max(0,groupChildOffset-pageSize);void loadGroupChildren()">{{ $t('apfUi.previous_group_page') }}</button>
                      <span>{{groupChildTotal?groupChildOffset+1:0}}–{{Math.min(groupChildOffset+groupChildren.length,groupChildTotal)}} / {{groupChildTotal}}</span>
                      <button type="button" :disabled="groupChildOffset+groupChildren.length>=groupChildTotal||loading||busy" @click="groupChildOffset+=pageSize;void loadGroupChildren()">{{ $t('apfUi.next_group_page') }}</button>
                    </nav>
                  </td></tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
        <section v-if="preview" class="trash-preview" :aria-label="$t('apfUi.permanent_deletion_preview')">
          <h3>{{ $t('apfUi.deletion_scope') }}</h3><p>{{ $t('apfUi.photos_value_managed_files_value_total_value', { p0: (preview.photo_count), p1: (preview.managed_file_count), p2: (bytes(preview.managed_bytes)) }) }}</p>
          <p v-if="preview.tasks.length" class="trash-error">{{ $t('apfUi.import_tasks_still_hold_these_items_value_cancel_them_through_the_impo', { p0: (preview.tasks.join('、')) }) }}</p>
          <div v-if="preview.references.length"><h4>{{ $t('apfUi.value_project_or_group_references_value', { p0: preview.references.some(reference=>reference.kind==='calibration')?$t('apfUi.project_group_or_calibration_references'):$t('apfUi.included_in_cleanup'), p1: preview.references.length }) }}</h4><p v-for="reference in preview.references" :key="reference.id">{{ $t('apfUi.value_value_version_value', { p0: reference.name, p1: reference.kind==='project_asset'?$t('apfUi.project_photos'):reference.kind==='project_dataset'?$t('apfUi.project_image_groups'):reference.kind==='calibration'?$t('apfUi.retained_calibration_references'):$t('apfUi.image_group_members'), p2: reference.version }) }}</p></div>
          <p v-if="preview.references.some(reference=>reference.kind==='calibration')" role="alert">{{ $t('apfUi.historical_versions_of_other_groups_still_reference_this_calibration_t') }}</p>
        </section>
      </div>
      <footer class="trash-footer">
        <nav class="trash-pages" :aria-label="$t('apfUi.trash_pagination')">
          <button type="button" :disabled="offset===0||loading||busy" @click="offset=Math.max(0,offset-pageSize);void load()">{{ $t('apfUi.previous_page') }}</button>
          <span>{{total?offset+1:0}}–{{Math.min(offset+rows.length,total)}} / {{total}}</span>
          <button type="button" :disabled="offset+rows.length>=total||loading||busy" @click="offset+=pageSize;void load()">{{ $t('apfUi.next_page') }}</button>
        </nav>
        <div class="trash-actions">
          <span class="trash-selection">{{ $t('apfUi.selected_value', { p0: (selected.size) }) }}</span>
          <button type="button" :disabled="!selected.size||busy||selectionRows().some(row=>[...rows,...groupChildren].find(item=>item.id===row.id)?.cleanup_status!=='trash')" @click="restore">{{ $t('apfUi.restore') }}</button>
          <button type="button" class="trash-danger" :disabled="!selected.size||busy" @click="requestPreview">{{ $t('apfUi.permanently_delete') }}</button>
        </div>
      </footer>
      <div v-if="deleteConfirm" class="trash-confirm" role="alertdialog" aria-modal="true">
        <h3>{{ $t('apfUi.confirm_permanent_deletion') }}</h3><p>{{ $t('apfUi.permanently_remove_value_records_value_photos_value_managed_files_valu', { p0: (preview?.items.length), p1: (preview?.photo_count), p2: (preview?.managed_file_count), p3: (bytes(preview?.managed_bytes??0)), p4: (preview?.references.length) }) }}</p>
        <p v-if="preview?.references.length">{{[...new Set(preview.references.map(reference=>reference.name))].join('、')}}</p>
        <div class="trash-actions">
          <button type="button" :disabled="busy" @click="deleteConfirm=false">{{ $t('apfUi.cancel') }}</button>
          <button type="button" class="trash-danger" :disabled="busy" @click="permanentlyDelete">{{ $t('apfUi.confirm_permanent_deletion') }}</button>
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
