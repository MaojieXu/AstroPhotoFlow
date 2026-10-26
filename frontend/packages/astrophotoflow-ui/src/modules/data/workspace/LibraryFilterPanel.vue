<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { assetApi } from '../api/index'
import { libraryFilterOptionsSchema } from '../api/contracts'

type Options = ReturnType<typeof libraryFilterOptionsSchema.parse>
type Filters = Record<string, string[] | string>
type Group = {key:string;label:string;values:string[];labels?:Array<{id:string;name:string}>}
const props = defineProps<{ filters: Filters; anchor?: HTMLButtonElement }>()
const emit = defineEmits<{ apply: [filters: Filters]; cancel: [] }>()
const options = ref<Options>()
const draft = ref<Filters>(JSON.parse(JSON.stringify(props.filters)))
const error = ref('')
const panel = ref<HTMLElement>()
const placement = ref({left:10,top:54,width:380,height:400,maxWidth:420,maxHeight:560,minWidth:280,minHeight:240})
const numericFields = [
  ['exposure_seconds','单帧曝光（秒）'],['integration_seconds','累计曝光（秒）'],
  ['sensor_temperature_c','温度（°C）'],['iso','ISO'],['gain','Gain'],['offset','Offset']
] as const
const groups = ref<Group[]>([])
let optionsRequest = 0
let resizeObserver:ResizeObserver|undefined

function copyFilters(value:Filters):Filters { return JSON.parse(JSON.stringify(value)) }
function selected(key:string) { return (draft.value[key] as string[]|undefined)??[] }
function toggle(key:string,value:string) {
  const next=new Set(selected(key))
  next.has(value)?next.delete(value):next.add(value)
  draft.value[key]=[...next]
  apply()
}
function apply(){emit('apply',copyFilters(draft.value))}
function reset(){draft.value={};apply()}
function binLabel(value:string){const [x,y]=value.split('x');return x===y?'Bin'+x:'Bin'+x+'×'+y}
function bound(key:string,side:'min'|'max'){
  const value=draft.value[key+'_'+side]
  return value===undefined||value===''?options.value?.numeric_ranges[key]?.[side]??0:Number(value)
}
function changeBound(key:string,side:'min'|'max',event:Event){
  const range=options.value?.numeric_ranges[key]
  if(!range)return
  const value=Number((event.target as HTMLInputElement).value)
  const other=bound(key,side==='min'?'max':'min')
  if(side==='min')draft.value[key+'_min']=String(Math.min(value,other))
  else draft.value[key+'_max']=String(Math.max(value,other))
}
function step(key:string){return key==='sensor_temperature_c'||key==='iso'?'1':'any'}
function placePanel(){
  const container=panel.value?.parentElement
  if(!container||!props.anchor)return
  const containerRect=container.getBoundingClientRect()
  const anchorRect=props.anchor.getBoundingClientRect()
  const edge=10,gap=8
  const width=Math.min(420,Math.max(0,container.clientWidth-edge*2))
  const maxHeight=Math.min(560,window.innerHeight*0.65,Math.max(0,container.clientHeight-edge*2))
  const below=Math.max(0,containerRect.bottom-anchorRect.bottom-gap-edge)
  const above=Math.max(0,anchorRect.top-containerRect.top-gap-edge)
  const openAbove=below<Math.min(320,maxHeight)&&above>below
  const height=Math.max(0,Math.min(maxHeight,openAbove?above:below))
  const left=Math.min(Math.max(edge,anchorRect.right-containerRect.left+container.scrollLeft-width),Math.max(edge,container.clientWidth-width-edge))
  const top=openAbove
    ? anchorRect.top-containerRect.top+container.scrollTop-gap-height
    : anchorRect.bottom-containerRect.top+container.scrollTop+gap
  const maxPanelWidth=Math.max(0,container.clientWidth-(left-container.scrollLeft)-edge)
  const maxPanelHeight=Math.max(0,Math.min(window.innerHeight*0.9,container.clientHeight-(top-container.scrollTop)-edge))
  placement.value={
    left,top,width,height,maxWidth:maxPanelWidth,maxHeight:maxPanelHeight,
    minWidth:Math.min(280,maxPanelWidth),minHeight:Math.min(240,maxPanelHeight)
  }
}
async function loadOptions(){
  const request=++optionsRequest
  try{
    const result=await assetApi.get('/astrophotoflow/api/v1/library/filter-options',libraryFilterOptionsSchema)
    if(request!==optionsRequest)return
    options.value=result
    groups.value=[
      {key:'frame_classes',label:'素材形态',values:result.frame_classes},
      {key:'frame_types',label:'帧用途',values:result.frame_types},
      {key:'roles',label:'分类',values:result.roles},
      {key:'camera_id',label:'相机',values:result.equipment.camera_id.map(item=>item.id),labels:result.equipment.camera_id},
      {key:'optical_system_id',label:'成像系统',values:result.equipment.optical_system_id.map(item=>item.id),labels:result.equipment.optical_system_id},
      {key:'filter_id',label:'滤镜',values:result.equipment.filter_id.map(item=>item.id),labels:result.equipment.filter_id},
      {key:'parameter_mode',label:'增益模式',values:result.parameter_modes},
      {key:'binning',label:'Bin',values:result.bin_values}
    ]
    await nextTick()
    placePanel()
  }catch{error.value='无法读取素材库筛选选项。'}
}
watch(()=>props.filters,value=>{draft.value=copyFilters(value)},{deep:true})
onMounted(()=>{
  void loadOptions()
  placePanel()
  if(panel.value?.parentElement){
    resizeObserver=new ResizeObserver(placePanel)
    resizeObserver.observe(panel.value.parentElement)
    if(props.anchor)resizeObserver.observe(props.anchor)
  }
  window.addEventListener('resize',placePanel)
})
onBeforeUnmount(()=>{optionsRequest++;resizeObserver?.disconnect();window.removeEventListener('resize',placePanel)})
</script>

<template>
  <section ref="panel" class="apf-filter-panel" aria-label="素材筛选"
    :style="{left:placement.left+'px',top:placement.top+'px',width:placement.width+'px',height:placement.height+'px',minWidth:placement.minWidth+'px',minHeight:placement.minHeight+'px',maxWidth:placement.maxWidth+'px',maxHeight:placement.maxHeight+'px'}" @pointerdown.stop>
    <header><strong>筛选素材</strong></header>
    <div class="apf-filter-content">
      <p v-if="error" class="apf-error" role="alert">{{error}}</p>
      <template v-if="options">
        <fieldset v-for="group in groups.filter(item=>item.values.length)" :key="group.key">
          <legend>{{group.label}}</legend>
          <label v-for="value in group.values" :key="value" class="apf-filter-choice">
            <input type="checkbox" :checked="selected(group.key).includes(value)" @change="toggle(group.key,value)" />
            {{group.labels?.find(item=>item.id===value)?.name ?? (group.key==='binning'?binLabel(value):value)}}
          </label>
        </fieldset>
        <template v-for="[key,label] in numericFields" :key="key">
          <fieldset v-if="options.numeric_ranges[key]" class="apf-filter-range">
            <legend>{{label}} · {{options.numeric_ranges[key].min}}–{{options.numeric_ranges[key].max}}</legend>
            <template v-if="options.numeric_ranges[key].min!==options.numeric_ranges[key].max">
              <label class="apf-range-bound"><span>最小值 <output>{{bound(key,'min')}}</output></span>
                <input type="range" :min="options.numeric_ranges[key].min" :max="options.numeric_ranges[key].max" :step="step(key)"
                  :value="bound(key,'min')" :aria-label="label+' 最小值'" @input="changeBound(key,'min',$event)" @change="apply" />
              </label>
              <label class="apf-range-bound"><span>最大值 <output>{{bound(key,'max')}}</output></span>
                <input type="range" :min="options.numeric_ranges[key].min" :max="options.numeric_ranges[key].max" :step="step(key)"
                  :value="bound(key,'max')" :aria-label="label+' 最大值'" @input="changeBound(key,'max',$event)" @change="apply" />
              </label>
            </template>
            <p v-else class="apf-single-range">{{options.numeric_ranges[key].min}}</p>
          </fieldset>
        </template>
      </template>
    </div>
    <footer><button type="button" @pointerdown.stop @click="reset">重置</button><button type="button" @pointerdown.stop @click="emit('cancel')">关闭</button></footer>
  </section>
</template>

<style scoped>
.apf-filter-panel{position:absolute;z-index:7;display:flex;flex-direction:column;box-sizing:border-box;min-width:0;min-height:0;max-width:calc(100% - 20px);max-height:65vh;overflow:hidden;padding:0;background:var(--comfy-menu-bg,#272727);border:1px solid var(--border-color,#555);border-radius:8px;box-shadow:0 8px 30px #0009}
.apf-filter-panel header,.apf-filter-panel footer{display:flex;flex:none;align-items:center;gap:8px;padding:10px 12px}.apf-filter-panel header{border-bottom:1px solid var(--border-color,#555)}.apf-filter-content{flex:1 1 auto;min-height:0;overflow-y:auto;padding:4px 12px}.apf-filter-panel fieldset{display:flex;flex-wrap:wrap;gap:8px;border:0;border-top:1px solid var(--border-color,#555);padding:8px 0;margin:8px 0}.apf-filter-panel fieldset.apf-filter-range{display:block}.apf-filter-panel legend{padding:0 5px}.apf-filter-choice{display:flex;align-items:center;gap:5px}.apf-range-bound{display:block;margin:8px}.apf-range-bound span{display:flex;justify-content:space-between;margin-bottom:3px;color:var(--descrip-text,#999);font-size:12px}.apf-range-bound output{color:var(--input-text,#ddd);font-variant-numeric:tabular-nums}.apf-range-bound input{display:block;box-sizing:border-box;width:100%;height:24px;margin:0;padding:0;accent-color:var(--content-preview-border,#8aa8d8)}.apf-filter-panel footer{justify-content:flex-end;border-top:1px solid var(--border-color,#555)}.apf-single-range{margin:4px 8px;color:var(--descrip-text,#999)}.apf-error{color:#faa}
.apf-filter-panel{resize:both}
.apf-filter-panel footer{padding-right:26px}
</style>
