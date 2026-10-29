import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import LibraryCheckbox from '@ui/modules/data/workspace/LibraryCheckbox.vue'
import LibraryMenu from '@ui/modules/data/workspace/LibraryMenu.vue'
import LibraryTabs from '@ui/modules/data/workspace/LibraryTabs.vue'
import { libraryControlsKey } from '@ui/modules/data/workspace/libraryControls'

const checkbox=defineComponent({props:{modelValue:[Boolean,String]},emits:['update:modelValue'],template:'<button :data-value="modelValue" @click="$emit(\'update:modelValue\',true)">Toggle</button>'})
const menu=defineComponent({props:{open:Boolean,items:Array},emits:['update:open'],template:'<div><slot name="trigger" /><slot /></div>'})
const tabs=defineComponent({props:{modelValue:String},emits:['update:modelValue'],template:'<div><slot /></div>'})
const tabsList=defineComponent({template:'<div role="tablist"><slot /></div>'})
const tabsTrigger=defineComponent({props:{value:String},template:'<button role="tab"><slot /></button>'})
const controls={button:tabsTrigger,input:checkbox,formItem:tabs,dialog:tabs,multiSelect:tabs,select:tabs,textarea:tabs,checkbox,menu,tabs,tabsList,tabsTrigger}
const global={provide:{[libraryControlsKey]:controls}}

describe('library native control adapters',()=>{
  it('passes mixed checkbox state to the injected control and emits a boolean selection',async()=>{
    const wrapper=mount(LibraryCheckbox,{props:{modelValue:false,indeterminate:true,label:'全选当前页'},global})
    expect(wrapper.get('button').attributes('data-value')).toBe('indeterminate')
    expect(wrapper.find('input').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[true]])
    wrapper.unmount()
  })

  it('passes menu options to the injected menu and closes through its public operation',async()=>{
    const command=vi.fn()
    const items=[{label:'批量管理',command}]
    const wrapper=mount(LibraryMenu,{props:{items},global})
    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.getComponent(menu).props('items')).toEqual(items)
    wrapper.getComponent(menu).vm.$emit('update:open',true)
    await wrapper.vm.$nextTick()
    expect(wrapper.getComponent(menu).props('open')).toBe(true)
    wrapper.vm.close()
    await wrapper.vm.$nextTick()
    expect(wrapper.getComponent(menu).props('open')).toBe(false)
    wrapper.unmount()
  })

  it('forwards controlled radio groups to the native menu and selects through the HTML entry',async()=>{
    const command=vi.fn()
    const items=[{label:'显示方式',radioGroup:{value:'simple',options:[{value:'simple',label:'简约',command},{value:'detail',label:'细节',command}]}}]
    const native=mount(LibraryMenu,{props:{items},global})
    expect(native.getComponent(menu).props('items')).toEqual(items)
    native.unmount()
    const fallback=mount(LibraryMenu,{props:{items}})
    expect(fallback.get('select[aria-label="显示方式"]').element).toHaveProperty('value','simple')
    await fallback.get('select').setValue('detail')
    expect(command).toHaveBeenCalledOnce()
    expect(fallback.get('details').element.open).toBe(false)
    await fallback.setProps({items:[{...items[0],disabled:true}]})
    expect(fallback.get('select').attributes('disabled')).toBeDefined()
    fallback.unmount()
  })

  it('keeps the native tab selection controlled and forwards the requested section',async()=>{
    const wrapper=mount(LibraryTabs,{props:{value:'equipment',label:'设备类别',options:[{value:'equipment',label:'我的设备'},{value:'equipment-setups',label:'设备组合'}]},global})
    expect(wrapper.getComponent(tabs).props('modelValue')).toBe('equipment')
    expect(wrapper.get('button[aria-current="page"]').text()).toBe('我的设备')
    wrapper.getComponent(tabs).vm.$emit('update:modelValue','equipment-setups')
    expect(wrapper.emitted('change')).toEqual([['equipment-setups']])
    expect(wrapper.getComponent(tabs).props('modelValue')).toBe('equipment')
    wrapper.unmount()
  })
})
