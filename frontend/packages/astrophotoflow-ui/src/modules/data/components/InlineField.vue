<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { nextTick, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  value: string | number | null | undefined
  display?: string
  title?: string
  editValue?: string
  activation?: 'click' | 'doubleclick'
  kind?: 'text' | 'number' | 'textarea' | 'select'
  choices?: Array<{value:string;label:string;disabled?:boolean}>
  choicesMessage?: string
  step?: number | 'any'
  integer?: boolean
  save: (value: string | number | null) => Promise<void>
}>(), {kind:'text',choices:()=>[],activation:'doubleclick',step:'any',integer:false})
const emit=defineEmits<{cancelled:[]}>()
const editing = ref(false)
const saving = ref(false)
const editorFocused = ref(false)
const editor = ref<HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement>()
const saveAtEditStart = ref<typeof props.save>()
const draft = ref('')
const error = ref('')
const initialDraft = ref('')
watch(() => props.value, value => { if (!editing.value) draft.value = value == null ? '' : String(value) }, {immediate:true})
function begin() {
  if(editing.value||saving.value)return
  saveAtEditStart.value=props.save
  draft.value = props.editValue ?? (props.value==null?'':String(props.value))
  initialDraft.value=draft.value
  error.value=''
  editorFocused.value=false
  editing.value=true
  void nextTick(() => {
    editor.value?.focus()
    if(props.kind==='select'&&editor.value instanceof HTMLSelectElement&&'showPicker' in editor.value){
      try{editor.value.showPicker()}
      catch{error.value=uiT('apfUi.could_not_expand_the_options_open_the_list_with_the_keyboard')}
    }
  })
}
function cancel() {
  if(!editing.value)return
  editing.value=false
  editorFocused.value=false
  saveAtEditStart.value=undefined
  error.value=''
  draft.value=props.display??(props.value==null?'':String(props.value))
  emit('cancelled')
}
function activate(){if(props.activation==='click')begin()}
function activateDoubleClick(){begin()}
async function commit() {
  if(!editing.value||saving.value)return
  if(draft.value===initialDraft.value){editing.value=false;editorFocused.value=false;saveAtEditStart.value=undefined;emit('cancelled');return}
  const next=props.kind==='number'?(draft.value===''?null:Number(draft.value)):draft.value
  const original=props.value
  const originalNumber=original==null||original===''?null:Number(original)
  if(props.kind==='number'&&((next===null&&originalNumber===null)||(next!==null&&Number.isFinite(originalNumber)&&next===originalNumber))){
    editing.value=false
    editorFocused.value=false
    saveAtEditStart.value=undefined
    emit('cancelled')
    return
  }
  if(props.kind!=='number'&&draft.value===initialDraft.value){editing.value=false;editorFocused.value=false;saveAtEditStart.value=undefined;emit('cancelled');return}
  saving.value=true;error.value=''
  try{await (saveAtEditStart.value??props.save)(next);editing.value=false;editorFocused.value=false;saveAtEditStart.value=undefined}
  catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_save');await nextTick();editor.value?.focus()}
  finally{saving.value=false}
}
function keydown(event:KeyboardEvent){
  if(event.key==='Escape'){event.preventDefault();cancel()}
  else if(event.key==='Enter'&&props.kind!=='textarea'){event.preventDefault();void commit()}
}
function keyup(event:KeyboardEvent){
  if(props.kind==='select'&&event.key==='Escape'&&editing.value){event.preventDefault();cancel()}
}
function focusout(event:FocusEvent){
  if(!editing.value||!editorFocused.value)return
  const root=event.currentTarget as HTMLElement
  if(event.relatedTarget instanceof Node&&root.contains(event.relatedTarget))return
  if(!saving.value)void commit()
}
function focusin(event:FocusEvent){if(editing.value&&event.target===editor.value)editorFocused.value=true}
</script>

<template>
  <span class="apf-inline-field" @focusin="focusin" @focusout="focusout">
    <template v-if="editing">
      <textarea v-if="kind==='textarea'" ref="editor" v-model="draft" rows="3" :disabled="saving" @keydown="keydown" />
      <select v-else-if="kind==='select'" ref="editor" v-model="draft" :disabled="saving" @keydown="keydown" @keyup="keyup">
        <option v-for="choice in choices" :key="choice.value" :value="choice.value" :disabled="choice.disabled">{{choice.label}}</option>
        <option v-if="choicesMessage" disabled value="__apf_choices_message__">{{choicesMessage}}</option>
      </select>
      <input v-else ref="editor" v-model="draft" :type="kind==='number'?'number':'text'" :step="kind==='number'?(integer?'1':step):undefined" :disabled="saving" @keydown="keydown" />
      <small v-if="saving">{{ $t('apfUi.saving') }}</small><small v-if="error" class="apf-inline-error" role="alert">{{error}}</small>
    </template>
    <button v-else type="button" class="apf-inline-value" :title="title ?? (activation==='doubleclick'?$t('apfUi.double_click_or_press_enter_to_edit'):undefined)" @click="activate" @dblclick.stop.prevent="activateDoubleClick" @keydown.enter.stop.prevent="begin" @keydown.space.stop.prevent="begin">{{display ?? (value===null||value===undefined||value===''?$t('apfUi.not_set'):value)}}<i aria-hidden="true" class="pi pi-pencil apf-edit-icon" /></button>
  </span>
</template>

<style scoped>
.apf-inline-field{display:inline-flex;min-width:80px;max-width:100%;flex-direction:column;gap:3px}.apf-inline-field input,.apf-inline-field select,.apf-inline-field textarea{width:100%;min-width:0;padding:5px 7px;color:var(--input-text,#ddd);background:var(--comfy-input-bg,#222);border:1px solid var(--border-color,#555);border-radius:5px;font:inherit}.apf-inline-value{max-width:100%;overflow-wrap:anywhere;text-align:left;white-space:pre-wrap;background:transparent;color:inherit}.apf-inline-error{color:#faa;white-space:normal}
</style>
