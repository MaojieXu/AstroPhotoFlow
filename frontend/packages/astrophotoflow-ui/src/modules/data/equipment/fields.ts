import type { Equipment } from '../api/contracts'
import { uiT } from '../../../core/i18n'

type InputField = { key: string; label: string; unit?: string; type?: string; options?: string[]; integer?: boolean }

export const specFields: Record<string, InputField[]> = {
  camera: [
    { key: 'sensor_width_px', get label() { return uiT('apfUi.sensor_width') }, unit: 'px', type: 'number', integer: true },
    { key: 'sensor_height_px', get label() { return uiT('apfUi.sensor_height') }, unit: 'px', type: 'number', integer: true },
    { key: 'pixel_size_um', get label() { return uiT('apfUi.pixel_size') }, unit: 'µm', type: 'number' },
    { key: 'cfa_pattern', get label() { return uiT('apfUi.cfa_pattern') } }
  ],
  telescope: [
    { key: 'native_focal_length_mm', get label() { return uiT('apfUi.native_focal_length') }, unit: 'mm', type: 'number' }
  ],
  filter: [
    { key: 'channel', get label() { return uiT('apfUi.filter_channel') } },
    { key: 'bandwidth_nm', get label() { return uiT('apfUi.filter_bandwidth') }, unit: 'nm', type: 'number' },
  ],
}
export const cfaChoices=[
  {value:'',get label() { return uiT('apfUi.not_specified') }},{value:'MONO',get label() { return uiT('apfUi.no_cfa_monochrome') }},
  {value:'RGGB',label:'RGGB'},{value:'BGGR',label:'BGGR'},{value:'GRBG',label:'GRBG'},{value:'GBRG',label:'GBRG'},
  {value:'XTRANS',label:'X-Trans 6×6'},{value:'QUAD_BAYER',label:'Quad Bayer'}
]
export const equipmentKinds = ['camera', 'telescope', 'mount', 'filter'] as const
export const equipmentKindLabels:Record<string,string> = {get camera() { return uiT('apfUi.camera_dacf07') },get telescope() { return uiT('apfUi.telescope') },get mount() { return uiT('apfUi.mount') },get filter() { return uiT('apfUi.filter') },get optical_system() { return uiT('apfUi.telescope') }}
export const equipmentKindIcons:Record<string,string> = {camera:'icon-[lucide--camera]',telescope:'icon-[lucide--telescope]',mount:'icon-[lucide--axis-3d]',filter:'icon-[lucide--circle-dot]',}
export function specKind(field:InputField):'number'|'select'|'text'{
  return field.key==='cfa_pattern'||field.options?'select':field.type==='number'?'number':'text'
}
export function specChoices(field:InputField){
  if(field.key==='cfa_pattern')return cfaChoices
  if(field.options)return [{value:'',get label() { return uiT('apfUi.not_specified') }},...field.options.map(value=>({value,label:value}))]
  return []
}
export function specDisplay(field:InputField,value:unknown){
  if(value===null||value===undefined||value==='')return uiT('apfUi.not_specified')
  if(field.key==='cfa_pattern')return cfaLabel(value)
  if(field.options)return specChoices(field).find(choice=>choice.value===String(value))?.label??String(value)
  return String(value)
}
export function specValue(field:InputField,specs:Record<string,unknown>){
  return specs[field.key]
}
export function cfaLabel(value:unknown){
  if(value===null||value===undefined||value==='')return uiT('apfUi.not_specified')
  return ({get MONO() { return uiT('apfUi.no_cfa_monochrome') },XTRANS:'X-Trans 6×6',QUAD_BAYER:'Quad Bayer'} as Record<string,string>)[String(value)]??String(value??uiT('apfUi.not_specified'))
}

export function equipmentSubtitle(item: Pick<Equipment, 'kind' | 'name' | 'model'>): string {
  const model = item.model?.trim()
  return equipmentKindLabels[item.kind] + (model && model.toLocaleLowerCase() !== item.name.trim().toLocaleLowerCase() ? ' · ' + model : '')
}
