import {flushPromises,mount} from '@vue/test-utils'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import LibraryFilterPanel from '@ui/modules/data/workspace/LibraryFilterPanel.vue'

const {get}=vi.hoisted(()=>({get:vi.fn()}))
vi.mock('@ui/modules/data/api/index',()=>({assetApi:{get}}))

function rect(left:number,top:number,width:number,height:number):DOMRect{
  return {left,top,right:left+width,bottom:top+height,width,height,x:left,y:top,toJSON:()=>({})} as DOMRect
}

function mountPanel(filters:Record<string,string[]|string>={},containerRect=rect(100,50,800,600),anchorRect=rect(700,90,60,32)){
  const container=document.createElement('div')
  const anchor=document.createElement('button')
  vi.spyOn(anchor,'getBoundingClientRect').mockReturnValue(anchorRect)
  container.append(anchor)
  document.body.append(container)
  const wrapper=mount(LibraryFilterPanel,{props:{filters,anchor},attachTo:container})
  const parent=wrapper.element.parentElement!
  Object.defineProperty(parent,'clientWidth',{configurable:true,value:containerRect.width})
  Object.defineProperty(parent,'clientHeight',{configurable:true,value:containerRect.height})
  vi.spyOn(parent,'getBoundingClientRect').mockReturnValue(containerRect)
  if(anchor.parentElement!==parent)parent.append(anchor)
  window.dispatchEvent(new Event('resize'))
  return {wrapper,container}
}

beforeEach(()=>{
  vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
  get.mockReset().mockResolvedValue({
    frame_classes:['subframe'],frame_types:['light'],roles:['raw'],parameter_modes:['iso'],
    bin_values:['1x1'],equipment:{camera_id:[{id:'camera-id',name:'Camera 1'}],optical_system_id:[],filter_id:[]},
    numeric_ranges:{exposure_seconds:{min:0,max:30},sensor_temperature_c:{min:-10,max:0},iso:{min:100,max:800}}
  })
})
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();document.body.replaceChildren()})

describe('library filter panel',()=>{
  it('explains an empty facet response instead of presenting a blank filter form',async()=>{
    get.mockResolvedValue({frame_classes:[],frame_types:[],roles:[],parameter_modes:[],bin_values:[],equipment:{camera_id:[],optical_system_id:[],filter_id:[]},numeric_ranges:{}})
    const {wrapper}=mountPanel()
    await flushPromises()
    expect(wrapper.text()).toContain('还没有可筛选的素材资料')
    expect(wrapper.find('fieldset').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('正在读取筛选选项')
    wrapper.unmount()
  })
  it('uses only values returned from the full-library facets and applies checked values',async()=>{
    const {wrapper}=mountPanel()
    await flushPromises()
    expect(wrapper.text()).toContain('Camera 1')
    expect(wrapper.text()).toContain('单帧曝光（秒） · 0–30')
    const camera=wrapper.findAll('input[type=checkbox]').find(input=>input.element.parentElement?.textContent?.includes('Camera 1'))
    await camera!.setValue(true)
    expect(wrapper.emitted('apply')?.[0]?.[0]).toMatchObject({camera_id:['camera-id']})
  })

  it('cancel does not apply its draft',async()=>{
    const {wrapper}=mountPanel({frame_class:['subframe']})
    await flushPromises()
    expect(wrapper.find('header button').exists()).toBe(false)
    expect(wrapper.findAll('footer button').map(button=>button.text())).toEqual(['重置','关闭'])
    await wrapper.findAll('footer button').find(button=>button.text()==='关闭')!.trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('apply')).toBeUndefined()
  })

  it('applies single-frame exposure, temperature and ISO range changes',async()=>{
    const {wrapper}=mountPanel({camera_id:['camera-id']})
    await flushPromises()
    const exposure=wrapper.get('input[aria-label="单帧曝光（秒） 最小值"]')
    await exposure.setValue('10')
    await exposure.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({camera_id:['camera-id'],exposure_seconds_min:'10'})
    const temperature=wrapper.get('input[aria-label="温度（°C） 最小值"]')
    await temperature.setValue('-5')
    await temperature.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({camera_id:['camera-id'],exposure_seconds_min:'10',sensor_temperature_c_min:'-5'})
    const iso=wrapper.get('input[aria-label="ISO 最小值"]')
    await iso.setValue('400')
    await iso.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({camera_id:['camera-id'],exposure_seconds_min:'10',sensor_temperature_c_min:'-5',iso_min:'400'})
    expect(wrapper.find('footer').text()).toContain('重置')
    expect(wrapper.find('footer').text()).toContain('关闭')
    expect(wrapper.find('footer').text()).not.toContain('应用')
  })

  it('anchors below the filter button and stays within the library pane',async()=>{
    const {wrapper}=mountPanel()
    await flushPromises()
    const style=wrapper.get('.apf-filter-panel').attributes('style')
    expect(style).toContain('left: 240px')
    expect(style).toContain('top: 80px')
    expect(style).toContain('width: 420px')
    expect(style).toContain(`height: ${Math.min(560,window.innerHeight*0.65,580,510)}px`)
    wrapper.unmount()
  })

  it('opens upward when there is not enough room below and fits narrow panes',async()=>{
    const {wrapper}=mountPanel({},rect(100,50,320,600),rect(120,580,60,32))
    await flushPromises()
    const style=wrapper.get('.apf-filter-panel').attributes('style')
    expect(style).toContain('left: 10px')
    expect(style).toContain('width: 300px')
    expect(Number((style??'').match(/top: ([\d.]+)px/)?.[1])).toBeCloseTo(22.8)
    wrapper.unmount()
  })
})
