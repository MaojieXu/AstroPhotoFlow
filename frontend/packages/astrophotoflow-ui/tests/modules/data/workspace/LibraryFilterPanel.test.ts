import {flushPromises,mount} from '@vue/test-utils'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import { h, ref } from 'vue'
import type { LibraryFilterOptions } from '@ui/generated/api/types.gen'
import { focusManager } from '@tanstack/vue-query'
import LibraryFilterPanel from '@ui/modules/data/library/LibraryFilterPanel.vue'

const {get}=vi.hoisted(()=>({get:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get),assetApi:{get}}))

function rect(left:number,top:number,width:number,height:number):DOMRect{
  return {left,top,right:left+width,bottom:top+height,width,height,x:left,y:top,toJSON:()=>({})} as DOMRect
}

const mounted: ReturnType<typeof mount<typeof LibraryFilterPanel>>[] = []

function mountPanel(filters:Record<string,string[]|string>={},containerRect=rect(100,50,800,600),anchorRect=rect(700,90,60,32)){
  const container=document.createElement('div')
  const anchor=document.createElement('button')
  vi.spyOn(anchor,'getBoundingClientRect').mockReturnValue(anchorRect)
  container.append(anchor)
  document.body.append(container)
  const wrapper=mount(LibraryFilterPanel,{props:{filters,anchor,workspace:'/test-workspace'},attachTo:container})
  const parent=wrapper.element.parentElement!
  Object.defineProperty(parent,'clientWidth',{configurable:true,value:containerRect.width})
  Object.defineProperty(parent,'clientHeight',{configurable:true,value:containerRect.height})
  vi.spyOn(parent,'getBoundingClientRect').mockReturnValue(containerRect)
  if(anchor.parentElement!==parent)parent.append(anchor)
  window.dispatchEvent(new Event('resize'))
  mounted.push(wrapper)
  return {wrapper,container}
}

const facets = (): LibraryFilterOptions => ({
    frame_classes:['subframe'],frame_types:['light'],roles:['raw'],parameter_modes:['iso'],
    bin_values:['1x1'],equipment:{camera_id:[{id:'00000000-0000-4000-8000-000000000001',name:'Camera 1'}],optical_system_id:[],filter_id:[]},
    numeric_ranges:{exposure_seconds:{min:0,max:30},sensor_temperature_c:{min:-10,max:0},iso:{min:100,max:800}}
  })

beforeEach(()=>{
  vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
  get.mockReset().mockResolvedValue(facets())
})
afterEach(()=>{for(const wrapper of mounted.splice(0))if(wrapper.exists())wrapper.unmount();focusManager.setFocused(undefined);vi.useRealTimers();vi.unstubAllGlobals();document.body.replaceChildren()})

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
    expect(wrapper.emitted('apply')?.[0]?.[0]).toMatchObject({camera_id:['00000000-0000-4000-8000-000000000001']})
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
    const {wrapper}=mountPanel({camera_id:['00000000-0000-4000-8000-000000000001']})
    await flushPromises()
    const exposure=wrapper.get('input[aria-label="单帧曝光（秒） 最小值"]')
    await exposure.setValue('10')
    await exposure.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({camera_id:['00000000-0000-4000-8000-000000000001'],exposure_seconds_min:'10'})
    const temperature=wrapper.get('input[aria-label="温度（°C） 最小值"]')
    await temperature.setValue('-5')
    await temperature.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({camera_id:['00000000-0000-4000-8000-000000000001'],exposure_seconds_min:'10',sensor_temperature_c_min:'-5'})
    const iso=wrapper.get('input[aria-label="ISO 最小值"]')
    await iso.setValue('400')
    await iso.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({camera_id:['00000000-0000-4000-8000-000000000001'],exposure_seconds_min:'10',sensor_temperature_c_min:'-5',iso_min:'400'})
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
  it('refreshes facet metadata without overwriting an unfinished range draft', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    const { wrapper } = mountPanel()
    await flushPromises()
    const minimum = wrapper.get('input[aria-label="单帧曝光（秒） 最小值"]')
    ;(minimum.element as HTMLInputElement).value = '10'
    await minimum.trigger('input')
    expect(wrapper.emitted('apply')).toBeUndefined()
    const refreshed = facets()
    get.mockResolvedValue({ ...refreshed, numeric_ranges: { ...refreshed.numeric_ranges, exposure_seconds: { min: 0, max: 6 } } })
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(wrapper.text()).toContain('单帧曝光（秒） · 0–6')
    expect((minimum.element as HTMLInputElement).value).toBe('10')
    expect(wrapper.emitted('apply')).toBeUndefined()
    await minimum.trigger('change')
    expect(wrapper.emitted('apply')?.at(-1)?.[0]).toMatchObject({ exposure_seconds_min: '10' })
  })

  it('shares facet reads and reuses fresh results when panels reopen in the same application', async () => {
    const count = ref(2)
    const parent = mount({ setup: () => () => h('div', Array.from({ length: count.value }, (_, key) =>
      h(LibraryFilterPanel, { key, workspace: '/one', filters: {} }))) })
    try {
      await flushPromises()
      expect(parent.findAllComponents(LibraryFilterPanel)).toHaveLength(2)
      expect(get).toHaveBeenCalledTimes(1)
      count.value = 0
      await flushPromises()
      count.value = 2
      await flushPromises()
      expect(parent.text()).toContain('Camera 1')
      expect(get).toHaveBeenCalledTimes(1)
    } finally {
      parent.unmount()
    }
  })

  it('cancels old workspace reads and ignores their late facet response', async () => {
    const next: LibraryFilterOptions = {
      frame_classes: [], frame_types: [], roles: [], parameter_modes: [], bin_values: [],
      equipment: { camera_id: [], optical_system_id: [], filter_id: [] }, numeric_ranges: {}
    }
    let finishOld!: (value: typeof next) => void
    get.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    const { wrapper } = mountPanel()
    await flushPromises()
    const oldSignal = get.mock.calls[0][2] as AbortSignal
    get.mockResolvedValue(next)
    await wrapper.setProps({ workspace: '/two' })
    await flushPromises()
    expect(oldSignal.aborted).toBe(true)
    expect(wrapper.text()).toContain('还没有可筛选的素材资料')
    finishOld({ ...next, frame_types: ['light'] })
    await flushPromises()
    expect(wrapper.find('fieldset').exists()).toBe(false)
    wrapper.unmount()
  })

})
