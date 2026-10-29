import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LocalImportPicker from '@ui/modules/data/workspace/LocalImportPicker.vue'

const {send,get}=vi.hoisted(()=>({send:vi.fn(),get:vi.fn()}))
vi.mock('@ui/modules/data/api/index',()=>({assetApi:{send,get}}))
const files=[{path:'C:\\Images\\one.fit',name:'one.fit',size:100},{path:'D:\\Night\\two.fit',name:'two.fit',size:200}]
let wrapper:ReturnType<typeof mount>|undefined
beforeEach(()=>{get.mockReset();send.mockReset().mockResolvedValue({cancelled:false,files,name:'Images',folder:false})})
afterEach(()=>{wrapper?.unmount();wrapper=undefined})

describe('direct native local source selection',()=>{
  it('returns absolute files across drives without reading configured roots or uploading browser files',async()=>{
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'files'}})
    await flushPromises()
    expect(send.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/imports/select-local')
    expect(send.mock.calls[0][3]).toEqual({mode:'files'})
    expect(wrapper.emitted('selected')?.[0]).toEqual([files,'Images',false])
    expect(get).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('授权目录')
    expect(wrapper.find('input[type=file]').exists()).toBe(false)
  })

  it('closes a cancelled system chooser without submitting an import',async()=>{
    send.mockResolvedValue({cancelled:true,files:[],name:null,folder:true})
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'folder'}})
    await flushPromises()
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('selected')).toBeUndefined()
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('explains empty folder selection and supports choosing again',async()=>{
    send.mockResolvedValueOnce({cancelled:false,files:[],name:'Empty',folder:true})
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'folder'}})
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('当前层没有支持')
    expect(wrapper.text()).toContain('不包含子文件夹')
    send.mockResolvedValueOnce({cancelled:false,files,name:'Night',folder:true})
    await wrapper.findAll('button').find(button=>button.text()==='重新选择')!.trigger('click')
    await flushPromises()
    expect(wrapper.emitted('selected')?.[0]).toEqual([files,'Night',true])
  })

  it('ignores a late native selection after the dialog was closed',async()=>{
    let finish:((value:unknown)=>void)|undefined
    send.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'files'}})
    await wrapper.setProps({open:false})
    expect(send.mock.calls[0][4].signal.aborted).toBe(true)
    finish?.({cancelled:false,files,name:'Night',folder:false})
    await flushPromises()
    expect(wrapper.emitted('selected')).toBeUndefined()
  })

  it('aborts the native request immediately when cancel is clicked',async()=>{
    send.mockImplementation(()=>new Promise(()=>{}))
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'files'}})
    const signal:AbortSignal=send.mock.calls[0][4].signal
    expect(signal.aborted).toBe(false)
    await wrapper.findAll('button').find(button=>button.text()==='取消')!.trigger('click')
    expect(signal.aborted).toBe(true)
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('selected')).toBeUndefined()
  })

  it('aborts an outstanding chooser when the component is unmounted',()=>{
    send.mockImplementation(()=>new Promise(()=>{}))
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'folder'}})
    const signal:AbortSignal=send.mock.calls[0][4].signal
    wrapper.unmount()
    wrapper=undefined
    expect(signal.aborted).toBe(true)
  })

  it('does not launch duplicate requests when retry is clicked rapidly',async()=>{
    send.mockRejectedValueOnce(new Error('打开失败')).mockImplementation(()=>new Promise(()=>{}))
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'files'}})
    await flushPromises()
    const retry=wrapper.findAll('button').find(button=>button.text()==='重新选择')!
    await Promise.all([retry.trigger('click'),retry.trigger('click')])
    expect(send).toHaveBeenCalledTimes(2)
  })

  it('keeps a fresh selection separate from a cancelled request',async()=>{
    const finish:Array<(value:unknown)=>void>=[]
    send.mockImplementation(()=>new Promise(resolve=>{finish.push(resolve)}))
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'files'}})
    const first:AbortSignal=send.mock.calls[0][4].signal
    await wrapper.setProps({open:false})
    await wrapper.setProps({open:true})
    const second:AbortSignal=send.mock.calls[1][4].signal
    finish[0]({cancelled:false,files,name:'Old',folder:false})
    await flushPromises()
    expect(first.aborted).toBe(true)
    expect(second.aborted).toBe(false)
    expect(wrapper.emitted('selected')).toBeUndefined()
    finish[1]({cancelled:false,files,name:'New',folder:false})
    await flushPromises()
    expect(wrapper.emitted('selected')?.[0]).toEqual([files,'New',false])
  })

  it('keeps native chooser failures visible without redirecting to settings',async()=>{
    send.mockRejectedValue(new Error('本机桌面不可用'))
    wrapper=mount(LocalImportPicker,{props:{open:true,mode:'files'}})
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('本机桌面不可用')
    expect(wrapper.text()).not.toContain('工作台设置')
  })
})
