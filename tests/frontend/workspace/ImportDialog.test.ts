import {flushPromises,mount} from '@vue/test-utils'
import {beforeEach,describe,expect,it,vi} from 'vitest'
import ImportDialog from '@frontend/workspace/ImportDialog.vue'

const {get,send,upload}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),upload:vi.fn()}))
vi.mock('@frontend/assets/host-client',()=>({assetApi:{get,send,upload}}))

beforeEach(()=>{
  get.mockReset().mockResolvedValue({items:[],total:0,limit:200,offset:0})
  send.mockReset()
  upload.mockReset()
})

describe('import dialog defaults',()=>{
  it('clears prior metadata when a new import dialog opens',async()=>{
    const file=new File(['fits'],'first.fits')
    const wrapper=mount(ImportDialog,{props:{open:false,files:[file],createDataset:true,datasetName:'M31'}})
    await wrapper.setProps({open:true})
    await flushPromises()
    const bin=wrapper.findAll('label').find(label=>label.text().startsWith('Bin'))!.get('select').element as HTMLSelectElement
    expect(Array.from(bin.options,value=>value.value)).toEqual(['',...Array.from({length:16},(_,index)=>String(index+1))])
    const datasetName=wrapper.findAll('label').find(label=>label.text().startsWith('数据集名称'))!.get('input')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    const frameClass=wrapper.findAll('label').find(label=>label.text().startsWith('素材形态'))!.get('select')
    const parameterMode=wrapper.findAll('label').find(label=>label.text().startsWith('增益模式'))!.get('select')
    await datasetName.setValue('M31 session')
    await frameClass.setValue('masterframe')
    const frameType=wrapper.findAll('label').find(label=>label.text().startsWith('帧用途'))!.get('select')
    await frameType.setValue('dark')
    await parameterMode.setValue('iso')
    await wrapper.get('input[type="number"]').setValue('800')

    await wrapper.setProps({open:false})
    await wrapper.setProps({open:true,datasetName:'M42'})
    await flushPromises()

    expect(wrapper.findAll('label').find(label=>label.text().startsWith('数据集名称'))!.get('input').element).toHaveProperty('value','M42')
    expect(wrapper.findAll('label').some(label=>label.text().startsWith('素材形态'))).toBe(false)
    expect(wrapper.get('input[type="checkbox"]').element).toHaveProperty('checked',false)
    expect(wrapper.findAll('label').some(label=>label.text().startsWith('帧用途'))).toBe(false)
    expect(wrapper.findAll('label').find(label=>label.text().startsWith('增益模式'))!.get('select').element).toHaveProperty('value','')
    expect(wrapper.findAll('input[type="number"]').every(input=>(input.element as HTMLInputElement).value==='')).toBe(true)
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('')
  })
})

describe('import overrides',()=>{
  it('omits blank manual values and classification so file metadata and presets can supply them',async()=>{
    send.mockResolvedValue({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'})
    upload.mockResolvedValue(undefined)
    const wrapper=mount(ImportDialog,{props:{open:false,files:[new File(['fits'],'one.fits')]}})
    await wrapper.setProps({open:true})
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const body=send.mock.calls[0][3]
    expect(body).not.toHaveProperty('classification')
    expect(body.parameters).toEqual({})
    wrapper.unmount()
  })
  it('submits a whole-batch manual classification including an intentional unknown frame type',async()=>{
    send.mockResolvedValue({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'})
    upload.mockResolvedValue(undefined)
    const wrapper=mount(ImportDialog,{props:{open:false,files:[new File(['fits'],'one.fits')]}})
    await wrapper.setProps({open:true})
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.findAll('label').find(label=>label.text().startsWith('素材形态'))!.get('select').setValue('masterframe')
    await wrapper.findAll('label').find(label=>label.text().startsWith('单帧曝光'))!.get('input').setValue('0')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send.mock.calls[0][3].classification).toEqual({frame_class:'masterframe',frame_type:null})
    expect(send.mock.calls[0][3].parameters).toEqual({exposure_seconds:0})
    wrapper.unmount()
  })
})
