import {flushPromises,mount} from '@vue/test-utils'
import {describe,expect,it,vi} from 'vitest'
import {nextTick} from 'vue'
import InlineField from '@ui/modules/data/components/InlineField.vue'

async function doubleClick(wrapper:ReturnType<typeof mount>){
  const button=wrapper.get('button').element
  button.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:1}))
  await nextTick()
  button.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:2}))
  await nextTick()
  button.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}))
  await nextTick()
}

describe('inline field editing',()=>{
  it.each(['Enter',' '])('opens editing with %s and cancels without saving',async(key)=>{
    const save=vi.fn()
    const wrapper=mount(InlineField,{props:{value:'M31',save}})
    try{
      await wrapper.get('button').trigger('keydown',{key})
      expect(wrapper.get('input').element.value).toBe('M31')
      await wrapper.get('input').setValue('M42')
      await wrapper.get('input').trigger('keydown',{key:'Escape'})
      expect(wrapper.find('input').exists()).toBe(false)
      expect(save).not.toHaveBeenCalled()
    }finally{wrapper.unmount()}
  })
  it('saves one changed value when Enter is pressed',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(InlineField,{props:{value:'M31',save}})
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('input').exists()).toBe(false)
    await doubleClick(wrapper)
    await wrapper.get('input').setValue('M42')
    await wrapper.get('input').trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(save).toHaveBeenCalledOnce()
    expect(save).toHaveBeenCalledWith('M42')
    expect(wrapper.text()).toContain('M31')
  })

  it('does not save when the display button is clicked and then blurred without editing',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(InlineField,{props:{value:'M31',save},attachTo:document.body})
    await wrapper.get('button').trigger('click')
    await wrapper.get('button').trigger('blur')
    await flushPromises()
    expect(save).not.toHaveBeenCalled()
  })

  it('keeps the editor open when double-click replaces the focused display button',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(InlineField,{props:{value:'M31',save},attachTo:document.body})
    wrapper.get('button').element.focus()
    await doubleClick(wrapper)
    expect(wrapper.get('input').element.value).toBe('M31')
    expect(save).not.toHaveBeenCalled()
  })

  it('keeps the draft visible when saving fails',async()=>{
    const save=vi.fn().mockRejectedValue(new Error('revision conflict'))
    const wrapper=mount(InlineField,{props:{value:'M31',save}})
    await doubleClick(wrapper)
    await wrapper.get('input').setValue('M42')
    await wrapper.get('input').trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.get('input').element.value).toBe('M42')
    expect(wrapper.text()).toContain('revision conflict')
  })

  it('keeps the save target from the record that was being edited',async()=>{
    const saveOriginal=vi.fn().mockResolvedValue(undefined)
    const saveCurrent=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(InlineField,{props:{value:'M31',save:saveOriginal}})
    await doubleClick(wrapper)
    await wrapper.get('input').setValue('M42')
    await wrapper.setProps({value:'M101',save:saveCurrent})
    await wrapper.get('input').trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(saveOriginal).toHaveBeenCalledWith('M42')
    expect(saveCurrent).not.toHaveBeenCalled()
  })

  it('opens enum editing with the raw choice value rather than its display label',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(InlineField,{props:{
      value:'subframe',display:'单帧',kind:'select',
      choices:[{value:'subframe',label:'Subframe'},{value:'masterframe',label:'Masterframe'}],save
    }})
    await doubleClick(wrapper)
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('subframe')
    await wrapper.get('select').setValue('masterframe')
    await wrapper.get('select').trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(save).toHaveBeenCalledWith('masterframe')
  })

  it('opens the native choice picker from the real dblclick handler',async()=>{
    const prior=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'showPicker')
    const showPicker=vi.fn()
    Object.defineProperty(HTMLSelectElement.prototype,'showPicker',{configurable:true,value:showPicker})
    const wrapper=mount(InlineField,{props:{
      value:'camera-1',display:'Camera 1',kind:'select',
      choices:[{value:'camera-1',label:'Camera 1'},{value:'camera-2',label:'Camera 2'}],save:vi.fn().mockResolvedValue(undefined)
    }})
    await doubleClick(wrapper)
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('camera-1')
    expect(showPicker).toHaveBeenCalledOnce()
    wrapper.unmount()
    if(prior)Object.defineProperty(HTMLSelectElement.prototype,'showPicker',prior)
    else Reflect.deleteProperty(HTMLSelectElement.prototype,'showPicker')
  })

  it('cancels the active draft with Escape',async()=>{
    const save=vi.fn()
    const wrapper=mount(InlineField,{props:{value:'M31',save}})
    await doubleClick(wrapper)
    await wrapper.get('input').setValue('M42')
    await wrapper.get('input').trigger('keydown',{key:'Escape'})
    expect(wrapper.text()).toContain('M31')
    expect(save).not.toHaveBeenCalled()
  })

  it('cancels a native select after Escape closes its picker',async()=>{
    const save=vi.fn()
    const wrapper=mount(InlineField,{props:{value:'camera-1',kind:'select',choices:[
      {value:'camera-1',label:'Camera 1'},{value:'camera-2',label:'Camera 2'}
    ],save}})
    await doubleClick(wrapper)
    await wrapper.get('select').setValue('camera-2')
    await wrapper.get('select').trigger('keyup',{key:'Escape'})
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.text()).toContain('camera-1')
    expect(save).not.toHaveBeenCalled()
  })

  it('does not write the two-decimal display of an unchanged raw temperature',async()=>{
    const save=vi.fn()
    const wrapper=mount(InlineField,{props:{value:-10.129,display:'-10.12',kind:'number',save}})
    await doubleClick(wrapper)
    await wrapper.get('input').trigger('blur')
    await flushPromises()
    expect(save).not.toHaveBeenCalled()
  })
})
