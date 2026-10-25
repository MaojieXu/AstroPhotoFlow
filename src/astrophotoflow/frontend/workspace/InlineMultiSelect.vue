<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

type Choice={value:string;label:string;disabled?:boolean}
const props=defineProps<{
  value:string[]
  choices:Choice[]
  choicesMessage?:string
  save:(value:string[])=>Promise<void>
}>()
const emit=defineEmits<{cancelled:[]}>()
const editing=ref(false)
const saving=ref(false)
const editorFocused=ref(false)
const error=ref('')
const editor=ref<HTMLSelectElement>()
const saveAtEditStart=ref<typeof props.save>()
const draft=ref<string[]>([...props.value])
const initial=ref<string[]>([...props.value])
watch(()=>props.value,value=>{if(!editing.value)draft.value=[...value]},{deep:true,immediate:true})

function displayValue(){
  const selected=props.value.map(value=>props.choices.find(choice=>choice.value===value)?.label??value.slice(0,8))
  return selected.length?selected.join('、'):'未指定'
}
function begin(){
  if(editing.value||saving.value)return
  saveAtEditStart.value=props.save
  draft.value=[...props.value]
  initial.value=[...props.value]
  error.value=''
  editorFocused.value=false
  editing.value=true
  void nextTick(()=>editor.value?.focus())
}
function cancel(){
  if(!editing.value)return
  editing.value=false
  editorFocused.value=false
  saveAtEditStart.value=undefined
  error.value=''
  draft.value=[...initial.value]
  emit('cancelled')
}
function sameValues(left:string[],right:string[]){
  return left.length===right.length&&left.every(value=>right.includes(value))
}
async function commit(){
  if(!editing.value||saving.value)return
  if(sameValues(draft.value,initial.value)){editing.value=false;editorFocused.value=false;saveAtEditStart.value=undefined;emit('cancelled');return}
  saving.value=true
  error.value=''
  try{await (saveAtEditStart.value??props.save)([...draft.value]);editing.value=false;editorFocused.value=false;saveAtEditStart.value=undefined}
  catch(cause){error.value=cause instanceof Error?cause.message:'保存失败。';await nextTick();editor.value?.focus()}
  finally{saving.value=false}
}
function keydown(event:KeyboardEvent){
  if(event.key==='Escape'){event.preventDefault();cancel()}
  else if(event.key==='Enter'){event.preventDefault();void commit()}
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
  <span class="apf-inline-multi-select" @focusin="focusin" @focusout="focusout">
    <template v-if="editing">
      <select ref="editor" v-model="draft" multiple size="5" :disabled="saving" aria-label="拍摄设置" @keydown="keydown">
        <option v-for="choice in choices" :key="choice.value" :value="choice.value" :disabled="choice.disabled">{{choice.label}}</option>
        <option v-if="choicesMessage" disabled value="__apf_choices_message__">{{choicesMessage}}</option>
      </select>
      <small v-if="saving">保存中…</small><small v-if="error" class="apf-multi-error" role="alert">{{error}}</small>
    </template>
    <button v-else type="button" class="apf-inline-value" title="双击编辑" @dblclick.stop.prevent="begin">{{displayValue()}}</button>
  </span>
</template>

<style scoped>
.apf-inline-multi-select{display:inline-flex;min-width:80px;max-width:100%;flex-direction:column;gap:3px}.apf-inline-multi-select select{width:100%;min-width:0;padding:5px 7px;color:var(--input-text,#ddd);background:var(--comfy-input-bg,#222);border:1px solid var(--border-color,#555);border-radius:5px;font:inherit}.apf-inline-multi-select button{max-width:100%;padding:2px 4px;background:transparent;color:inherit;text-align:left;white-space:pre-wrap}.apf-multi-error{color:#faa;white-space:normal}
</style>
