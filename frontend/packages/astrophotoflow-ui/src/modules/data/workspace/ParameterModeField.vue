<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

type RawNumber = number | string | null | undefined
type ModeValues = { parameter_mode: string | null | undefined; iso: RawNumber; gain: RawNumber; offset: RawNumber }
type Changes = { parameter_mode?: string | null; iso?: number | null; gain?: number | null; offset?: number | null }

const props = defineProps<{
  value: ModeValues
  display: string
  unsetMode: 'standard' | null
  save: (changes: Changes) => Promise<void>
}>()
const emit = defineEmits<{ cancelled: [] }>()
const editing = ref(false)
const saving = ref(false)
const editorFocused = ref(false)
const error = ref('')
const modeEditor = ref<HTMLSelectElement>()
const isoEditor = ref<HTMLInputElement>()
const gainEditor = ref<HTMLInputElement>()
const offsetEditor = ref<HTMLInputElement>()
const saveAtEditStart = ref<typeof props.save>()
const modeDraft = ref('')
const isoDraft = ref('')
const gainDraft = ref('')
const offsetDraft = ref('')
const initial = ref({ mode: '', iso: '', gain: '', offset: '' })

function modeInput(value: string | null | undefined) {
  return value == null ? (props.unsetMode ?? '') : value
}

function numberInput(value: RawNumber) {
  return value == null || value === 'mixed' || value === 'partial' ? '' : String(value)
}

function begin() {
  if (editing.value || saving.value) return
  saveAtEditStart.value = props.save
  modeDraft.value = modeInput(props.value.parameter_mode)
  isoDraft.value = numberInput(props.value.iso)
  gainDraft.value = numberInput(props.value.gain)
  offsetDraft.value = numberInput(props.value.offset)
  initial.value = { mode: modeDraft.value, iso: isoDraft.value, gain: gainDraft.value, offset: offsetDraft.value }
  error.value = ''
  editorFocused.value = false
  editing.value = true
  void nextTick(() => {
    modeEditor.value?.focus()
    if (modeEditor.value && 'showPicker' in modeEditor.value) {
      try { modeEditor.value.showPicker() }
      catch { error.value = '增益模式选项未能展开，请使用键盘打开。' }
    }
  })
}

function cancel() {
  if (!editing.value) return
  editing.value = false
  editorFocused.value = false
  saveAtEditStart.value = undefined
  error.value = ''
  emit('cancelled')
}

function asNumber(value: string) {
  return value === '' ? null : Number(value)
}

function changedNumber(value: string, original: string) {
  if (value === original) return false
  const next = asNumber(value)
  const previous = asNumber(original)
  return !(next === null && previous === null) && !(next !== null && previous !== null && Number.isFinite(previous) && next === previous)
}

async function commit() {
  if (!editing.value || saving.value) return
  const mode = modeDraft.value === '' ? props.unsetMode : modeDraft.value
  const originalMode = props.value.parameter_mode
  const modeChanged = mode !== originalMode && !(modeInput(mode) === '' && modeInput(originalMode) === '')
  const changes: Changes = {}
  if (modeChanged) changes.parameter_mode = mode
  const activeMode = modeDraft.value
  if (activeMode === 'iso' && changedNumber(isoDraft.value, initial.value.iso)) changes.iso = asNumber(isoDraft.value)
  if (activeMode === 'gain' && changedNumber(gainDraft.value, initial.value.gain)) changes.gain = asNumber(gainDraft.value)
  if (activeMode === 'gain' && changedNumber(offsetDraft.value, initial.value.offset)) changes.offset = asNumber(offsetDraft.value)
  if (!Object.keys(changes).length) {
    editing.value = false
    editorFocused.value = false
    saveAtEditStart.value = undefined
    emit('cancelled')
    return
  }
  saving.value = true
  error.value = ''
  try {
    await (saveAtEditStart.value ?? props.save)(changes)
    editing.value = false
    editorFocused.value = false
    saveAtEditStart.value = undefined
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '保存失败。'
    await nextTick()
    ;(modeEditor.value ?? (activeMode === 'iso' ? isoEditor.value : gainEditor.value))?.focus()
  } finally {
    saving.value = false
  }
}

function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { event.preventDefault(); cancel() }
  else if (event.key === 'Enter') { event.preventDefault(); void commit() }
}
function keyup(event: KeyboardEvent) {
  if (event.key === 'Escape' && editing.value) { event.preventDefault(); cancel() }
}

function focusout(event: FocusEvent) {
  if (!editing.value || !editorFocused.value) return
  const root = event.currentTarget as HTMLElement
  if (event.relatedTarget instanceof Node && root.contains(event.relatedTarget)) return
  if (!saving.value) void commit()
}

function focusin(event:FocusEvent){
  if(editing.value&&(event.target===modeEditor.value||event.target===isoEditor.value||event.target===gainEditor.value||event.target===offsetEditor.value))editorFocused.value=true
}

watch(() => [props.value.parameter_mode, props.value.iso, props.value.gain, props.value.offset], () => {
  if (!editing.value) {
    modeDraft.value = modeInput(props.value.parameter_mode)
    isoDraft.value = numberInput(props.value.iso)
    gainDraft.value = numberInput(props.value.gain)
    offsetDraft.value = numberInput(props.value.offset)
  }
}, { immediate: true })
</script>

<template>
  <span class="apf-mode-field" @focusin="focusin" @focusout="focusout">
    <template v-if="editing">
      <select ref="modeEditor" v-model="modeDraft" :disabled="saving" @keydown="keydown" @keyup="keyup">
        <option :value="unsetMode ?? ''">未指定</option>
        <option value="mixed" disabled>混合</option>
        <option value="iso">ISO</option>
        <option value="gain">Gain／Offset</option>
      </select>
      <input v-if="modeDraft==='iso'" ref="isoEditor" v-model="isoDraft" type="number" min="1" step="1" placeholder="未指定" :disabled="saving" aria-label="ISO" @keydown="keydown" />
      <template v-else-if="modeDraft==='gain'">
        <input ref="gainEditor" v-model="gainDraft" type="number" step="any" :placeholder="value.gain==='mixed'?'混合':value.gain==='partial'?'部分缺失':'未指定'" :disabled="saving" aria-label="Gain" @keydown="keydown" />
        <span>/</span>
        <input ref="offsetEditor" v-model="offsetDraft" type="number" step="any" :placeholder="value.offset==='mixed'?'混合':value.offset==='partial'?'部分缺失':'未指定'" :disabled="saving" aria-label="Offset" @keydown="keydown" />
      </template>
      <small v-if="saving">保存中…</small><small v-if="error" class="apf-mode-error" role="alert">{{error}}</small>
    </template>
    <button v-else type="button" class="apf-inline-value" title="双击或按 Enter 编辑" @dblclick.stop.prevent="begin" @keydown.enter.stop.prevent="begin" @keydown.space.stop.prevent="begin">{{display}}<i aria-hidden="true" class="pi pi-pencil apf-edit-icon" /></button>
  </span>
</template>

<style scoped>
.apf-mode-field{display:inline-flex;min-width:80px;max-width:100%;align-items:center;gap:4px;flex-wrap:wrap}.apf-mode-field input,.apf-mode-field select{min-width:54px;max-width:100%;padding:5px 7px;color:var(--input-text,#ddd);background:var(--comfy-input-bg,#222);border:1px solid var(--border-color,#555);border-radius:5px;font:inherit}.apf-mode-field button{padding:2px 4px;background:transparent;color:inherit;text-align:left;white-space:pre-wrap}.apf-mode-error{flex-basis:100%;color:#faa;white-space:normal}
</style>
