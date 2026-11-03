import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import InlineCalibrationCell from '@ui/modules/data/library/InlineCalibrationCell.vue'
import LibraryTable from '@ui/modules/data/library/LibraryTable.vue'
import { calibrationCellLabel } from '@ui/modules/data/library/inlineCalibration'
import type { InlineCalibrationBinding } from '@ui/modules/data/library/inlineCalibration'
import type { LibraryCalibrationSlot } from '@ui/generated/api/types.gen'
import type { LibraryTableRow } from '@ui/modules/data/library/tableTypes'
import { ApiClientError } from '@ui/core/api/errors'

const api = vi.hoisted(() => ({search:vi.fn(),updateImage:vi.fn(),updateMembers:vi.fn()}))
vi.mock('@ui/modules/data/api/calibration', () => ({calibrationApi:api}))
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`
const unconfigured = (): LibraryCalibrationSlot => ({choice:{mode:'unconfigured'},source:'standalone',status:'unconfigured',check_state:'not_checked'})
const target = (name: string, n: number): LibraryCalibrationSlot => ({choice:{mode:'target',target:{kind:'asset_version',id:id(n)}},source:'member_override',status:'target',target_detail:{target:{kind:'asset_version',id:id(n)},asset_id:id(n+100),name,version_number:2,target_kind:'master',master_required:false}})
function binding(dataset = false): InlineCalibrationBinding {
  return {slot:'flat',label:'平场',value:unconfigured(),context:{workspaceId:`inline-${dataset}`,assetId:id(1),versionId:id(2),revision:4,bindingVersionId:null,
    dataset:dataset?{id:id(3),current_version_id:id(4),revision:5,followsCurrent:true}:undefined,
    saved:vi.fn().mockResolvedValue(undefined),runSave:(_key,operation)=>operation(),cancel:vi.fn()}}
}
let wrapper: ReturnType<typeof mount> | undefined
beforeEach(()=>{api.search.mockReset().mockResolvedValue({items:[{target:{kind:'asset_version',id:id(9)},name:'Master Flat H',version_number:2}],total:1,limit:200,offset:0});api.updateImage.mockReset().mockResolvedValue({});api.updateMembers.mockReset().mockResolvedValue({})})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks()})

describe('calibration directly in existing table cells',()=>{
  it('does not query or scientifically check while browsing, and keeps technical references out of text',()=>{
    const data=binding();data.value=target('Master Flat H',9)
    wrapper=mount(InlineCalibrationCell,{props:{binding:data}})
    expect(wrapper.text()).toBe('Master Flat H')
    expect(wrapper.text()).not.toContain(id(9))
    expect(wrapper.get('button').attributes('title')).toContain(id(9))
    expect(api.search).not.toHaveBeenCalled()
  })
  it('saves one optional standalone slot and never defaults an empty value to disabled',async()=>{
    const data=binding();wrapper=mount(InlineCalibrationCell,{props:{binding:data}})
    expect(wrapper.text()).toBe('未配置')
    await wrapper.get('button').trigger('dblclick');await flushPromises()
    const select=wrapper.get('select')
    expect(select.element.value).toBe('unconfigured')
    await select.setValue(id(9));await select.trigger('keydown',{key:'Enter'});await flushPromises()
    expect(api.updateImage).toHaveBeenCalledWith(id(1),id(2),expect.objectContaining({expected_revision:4,changes:{flat:{mode:'target',target:{kind:'asset_version',id:id(9)}}},accept_unknown:false}))
    expect(data.context?.saved).toHaveBeenCalled()
    expect(api.updateMembers).not.toHaveBeenCalled()
  })
  it('uses a member patch to restore inheritance without rewriting all members',async()=>{
    const data=binding(true);data.value=target('Flat A',8)
    wrapper=mount(InlineCalibrationCell,{props:{binding:data}})
    await wrapper.get('button').trigger('dblclick');await flushPromises()
    await wrapper.get('select').setValue('inherit');await wrapper.get('select').trigger('keydown',{key:'Enter'});await flushPromises()
    expect(api.updateMembers).toHaveBeenCalledWith(id(3),expect.objectContaining({expected_revision:5,base_version_id:id(4),members:[{asset_version_id:id(2),changes:{flat:{mode:'inherit'}}}]}))
    expect(api.updateImage).not.toHaveBeenCalled()
  })
  it('asks about the specific unknowns before accepting them and does not bypass scientific conflicts',async()=>{
    api.updateImage.mockRejectedValueOnce(new ApiClientError('Unknown','service',409,'CALIBRATION_UNKNOWN',undefined,[{path:'flat',message:'temperature unknown'}])).mockResolvedValueOnce({})
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(true)
    wrapper=mount(InlineCalibrationCell,{props:{binding:binding()}})
    await wrapper.get('button').trigger('dblclick');await flushPromises()
    await wrapper.get('select').setValue(id(9));await wrapper.get('select').trigger('keydown',{key:'Enter'});await flushPromises()
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('temperature unknown'))
    expect(api.updateImage.mock.calls[1][2].accept_unknown).toBe(true)
  })
  it('distinguishes group summaries, empty optional slots and non-applicable slots',()=>{
    expect(calibrationCellLabel({...unconfigured(),status:'mixed',choice:null})).toBe('多种')
    expect(calibrationCellLabel({...unconfigured(),status:'not_applicable'})).toBe('—')
    expect(calibrationCellLabel({...unconfigured(),status:'disabled',choice:{mode:'disabled'}})).toBe('不使用')
  })
  it('does not retry a known conflict as an accepted unknown',async()=>{
    api.updateImage.mockRejectedValue(new ApiClientError('Gain conflict','service',409,'CALIBRATION_CONFLICT'))
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(true)
    wrapper=mount(InlineCalibrationCell,{props:{binding:binding()}})
    await wrapper.get('button').trigger('dblclick');await flushPromises()
    await wrapper.get('select').setValue(id(9));await wrapper.get('select').trigger('keydown',{key:'Enter'});await flushPromises()
    expect(api.updateImage).toHaveBeenCalledTimes(1)
    expect(confirm).not.toHaveBeenCalled()
    expect(wrapper.get('[role="alert"]').text()).toBe('Gain conflict')
  })
  it('retains the revision captured when editing begins after a background row refresh',async()=>{
    const original=binding()
    wrapper=mount(InlineCalibrationCell,{props:{binding:original}})
    await wrapper.get('button').trigger('dblclick');await flushPromises()
    await wrapper.setProps({binding:{...original,context:{...original.context!,revision:9}}})
    await wrapper.get('select').setValue(id(9));await wrapper.get('select').trigger('keydown',{key:'Enter'});await flushPromises()
    expect(api.updateImage.mock.calls[0][2].expected_revision).toBe(4)
  })
  it('adds columns to the original table and keeps group exposure visible in compact mode',()=>{
    const field={value:'',save:vi.fn().mockResolvedValue(undefined)}
    const row:LibraryTableRow={key:'g',title:'M31',subtitle:'',dataset:true,video:false,selected:false,memberCount:2,mixedUse:false,readiness:'',parametersDisplay:'',parameterSource:'',storage:'',availability:'',exposureSummary:'10分',
      calibration:[{slot:'flat',label:'平场',value:{...unconfigured(),status:'mixed',choice:null}},{slot:'dark_flat',label:'暗平场',value:{...unconfigured(),status:'not_applicable'}}],
      fields:{name:{...field,value:'M31'},groupClass:field,groupType:field,assetClass:field,assetType:field,camera:field,
        parameters:{value:{parameter_mode:null,iso:null,gain:null,offset:null},display:'',unsetMode:null,save:field.save},exposure:field,temperature:field,binning:field,cfa:field,opticalSystem:field,filter:field,integration:field,status:field,notes:field,opticalSystemReference:field,filterReference:field,statusReference:field,notesReference:field}}
    wrapper=mount(LibraryTable,{props:{rows:[row],library:true,viewMode:'simple',sortable:true,sort:{by:'name',order:'asc'},selectMode:false,selectionAllowed:true,deleting:false,allSelected:false,partiallySelected:false}})
    expect(wrapper.findAll('table')).toHaveLength(1)
    expect(wrapper.get('thead').text()).toContain('平场')
    expect(wrapper.get('thead').text()).not.toContain('暗平场')
    expect(wrapper.get('.apf-group-total').text()).toBe('10分')
    expect(wrapper.text()).toContain('多种')
  })
})
