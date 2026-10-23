import {flushPromises,mount} from '@vue/test-utils'
import {describe,expect,it,vi} from 'vitest'
import {nextTick} from 'vue'
import ParameterModeField from './ParameterModeField.vue'

async function open(wrapper:ReturnType<typeof mount>){
  const button=wrapper.get('button').element
  button.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:1}))
  await nextTick()
  button.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:2}))
  await nextTick()
  button.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}))
  await nextTick()
}

describe('ISO and Gain composite editor',()=>{
  it('switches the visible input immediately and submits only changed values once',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(ParameterModeField,{props:{
      value:{parameter_mode:'iso',iso:800,gain:42,offset:12},display:'ISO · 800',unsetMode:'standard',save
    }})
    await open(wrapper)
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('iso')
    await wrapper.get('select').setValue('gain')
    expect(wrapper.find('input[aria-label="Gain"]').exists()).toBe(true)
    expect((wrapper.get('input[aria-label="Gain"]').element as HTMLInputElement).value).toBe('42')
    expect((wrapper.get('input[aria-label="Offset"]').element as HTMLInputElement).value).toBe('12')
    await wrapper.get('input[aria-label="Gain"]').setValue('55')
    await wrapper.get('input[aria-label="Gain"]').trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(save).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledWith({parameter_mode:'gain',gain:55})
  })

  it('keeps the composite editor open while it replaces the focused button',async()=>{
    const save=vi.fn()
    const wrapper=mount(ParameterModeField,{props:{
      value:{parameter_mode:'iso',iso:800,gain:null,offset:null},display:'ISO · 800',unsetMode:'standard',save
    }})
    wrapper.get('button').element.focus()
    await open(wrapper)
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('iso')
    expect((wrapper.get('input[aria-label="ISO"]').element as HTMLInputElement).value).toBe('800')
    expect(save).not.toHaveBeenCalled()
  })

  it('does not turn a mixed placeholder into a null write',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(ParameterModeField,{props:{
      value:{parameter_mode:'iso',iso:'partial',gain:'mixed',offset:null},display:'ISO · 800（部分缺失）',unsetMode:'standard',save
    }})
    await open(wrapper)
    expect((wrapper.get('input[aria-label="ISO"]').element as HTMLInputElement).value).toBe('')
    await wrapper.get('input[aria-label="ISO"]').trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(save).not.toHaveBeenCalled()
  })

  it('cancels the entire draft on Escape',async()=>{
    const save=vi.fn()
    const wrapper=mount(ParameterModeField,{props:{
      value:{parameter_mode:'standard',iso:800,gain:null,offset:null},display:'未指定',unsetMode:'standard',save
    }})
    await open(wrapper)
    await wrapper.get('select').setValue('iso')
    await wrapper.get('input[aria-label="ISO"]').setValue('400')
    await wrapper.get('input[aria-label="ISO"]').trigger('keydown',{key:'Escape'})
    expect(wrapper.text()).toContain('未指定')
    expect(save).not.toHaveBeenCalled()
  })

  it('cancels when Escape closes the native mode picker',async()=>{
    const save=vi.fn()
    const wrapper=mount(ParameterModeField,{props:{
      value:{parameter_mode:'iso',iso:800,gain:42,offset:12},display:'ISO · 800',unsetMode:'standard',save
    }})
    await open(wrapper)
    await wrapper.get('select').setValue('gain')
    await wrapper.get('select').trigger('keyup',{key:'Escape'})
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.text()).toContain('ISO · 800')
    expect(save).not.toHaveBeenCalled()
  })
})
