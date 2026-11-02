import { uiT } from '../../../core/i18n'
import type { ParameterDisplayValues } from '../library/summary'

export function binValue(parameters: Partial<Pick<ParameterDisplayValues, 'binning_x' | 'binning_y'>>) {
  const x=parameters.binning_x,y=parameters.binning_y
  if(x==null&&y==null)return null
  return x===y?'Bin'+x:'Bin'+String(x??'—')+'×'+String(y??'—')
}
export function binEditValue(parameters: Partial<Pick<ParameterDisplayValues, 'binning_x' | 'binning_y'>>){
  const x=parameters.binning_x,y=parameters.binning_y
  return x==null&&y==null?'':x===y&&typeof x==='number'&&x>=1&&x<=16?'Bin'+x:`legacy:${x??''}x${y??''}`
}
export function binEditChoices(parameters: Partial<Pick<ParameterDisplayValues, 'binning_x' | 'binning_y'>>){
  const current=binEditValue(parameters)
  return [{value:'',get label() { return uiT('apfUi.not_specified') }},...Array.from({length:16},(_,i)=>({value:'Bin'+(i+1),label:'Bin'+(i+1)})),
    ...(current.startsWith('legacy:')?[{value:current,label:binValue(parameters)+uiT('apfUi.current_value')}]:[])]
}
