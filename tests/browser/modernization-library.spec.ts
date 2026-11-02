import type { APIRequestContext } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { test as base, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { z } from '../../frontend/node_modules/zod/index.js'
import { readFile, writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { createSyntheticAsset } from './scientificAssets'
import { fileURLToPath } from 'node:url'
import { zAssetOut, zDatasetVersionOut, zLibraryItemPage, zServiceHealth, zServiceCapabilities, zNodeCapability, zSoftwarePackage, zSoftwarePackageDetails, zEquipmentSetupOut, zCapturePresetOut, zManagementTrashPreviewOut, zEquipmentPage, zConfigState, zSoftwareCallResult } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import { reportRoot as root, seedRoot } from './modernization-paths.mjs'

const seed = JSON.parse(await readFile(new URL(process.env.APF_BROWSER_SEED ?? 'indexed-browser-page-seed.json', seedRoot), 'utf8'))
const datasetId: string = seed.task.dataset_id
const groupName = 'G2 synthetic 52 frames'
const standaloneName = 'G7 browser standalone ' + randomUUID()
let standaloneId: string

const test = base.extend<{errors: string[]}>({
  errors: async ({page, context, baseURL}, use) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(String(error)))
    page.on('console',message=>{if(message.type()==='error'&&message.text().includes("Error calling extension 'AstroPhotoFlow."))errors.push(message.text())})
    await context.route('**/*', route => {
      const target = new URL(route.request().url())
      return target.origin === new URL(baseURL!).origin || !['http:', 'https:'].includes(target.protocol) ? route.continue() : route.abort()
    })
    await use(errors)
    expect(errors).toEqual([])
  },
})

test.beforeAll(async({request})=>{
  const response=await request.get('/astrophotoflow/api/v1/health')
  expect(response.ok()).toBe(true)
  const health=zServiceHealth.parse(await response.json())
  const normalized=(path:string)=>path.replaceAll('\\','/').toLowerCase()
  expect(normalized(health.workspace)).toBe(normalized(seed.workspace))
  const asset = await createSyntheticAsset(request, standaloneName)
  standaloneId = asset.id
  await writeFile(new URL('browser-standalone-' + asset.id + '.json', root), JSON.stringify(asset, null, 2))
})

test.afterAll(async ({ request }) => {
  if (!standaloneId) return
  const response = await request.get('/astrophotoflow/api/v1/library/assets/' + standaloneId)
  expect(response.status()).toBe(200)
  const current = zAssetOut.parse(await response.json())
  const archived = await request.patch('/astrophotoflow/api/v1/library/assets/' + standaloneId, {
    data: { base_revision: current.revision, status: 'archived' }
  })
  expect(archived.status()).toBe(200)
})

test('real summary, member pagination and zero-valued metadata edit', async ({page, errors}) => {
  const requests: string[] = []
  page.on('request', request => {if (request.url().includes('/datasets/')) requests.push(request.url())})
  const response = page.waitForResponse(response => response.request().method() === 'GET' && new URL(response.url()).pathname.endsWith('/library/items'))
  await page.goto('/')
  const body = zLibraryItemPage.parse(await (await response).json())
  const summary = body.items.find(item => item.entry_type === 'dataset' && item.id === datasetId)
  expect(summary?.member_count).toBe(52)
  expect(JSON.stringify(summary)).not.toContain('"members"')
  const workspace = page.locator('.apf-workspace')
  await expect(workspace).toBeVisible()
  const group = workspace.locator('.apf-assets-table tbody tr').filter({hasText: groupName})
  await expect(group).toHaveCount(1)
  await group.locator('.apf-member-open').click()
  await expect(workspace.getByRole('heading', {level: 1})).toContainText(groupName)
  const rows = workspace.locator('.apf-assets-table tbody tr')
  await expect(rows).toHaveCount(50)
  await workspace.getByRole('button', {name: '下一页', exact: true}).click()
  await expect(rows).toHaveCount(2)
  const pageRequest = requests.filter(url => url.includes('/members?')).at(-1)!
  expect(new URL(pageRequest).searchParams.get('offset')).toBe('50')
  expect(new URL(pageRequest).searchParams.get('limit')).toBe('50')
  expect(requests.some(url => new URL(url).pathname.match(/\/datasets\/[^/]+\/versions\/[^/]+$/))).toBe(false)
  const graphBefore = await page.evaluate(() => window.app?.graph.nodes.map(node => ({id: node.id, type: node.type})))
  const exposure = rows.first().locator('td').nth(5).locator('.apf-inline-value')
  async function saveExposure(value: string) {
    await exposure.dblclick()
    const editor = rows.first().locator('td').nth(5).getByRole('spinbutton')
    await editor.fill(value)
    const saved = page.waitForResponse(response => response.request().method() === 'PATCH' && response.url().includes('/library/assets/'))
    await editor.press('Enter')
    const result = await saved
    expect(result.status()).toBe(200)
    expect((await result.json()).parameters.exposure_seconds).toBe(Number(value))
    await expect(rows.first().locator('td').nth(5)).toContainText(value + ' s')
  }
  if ((await exposure.innerText()).trim() === '0 s') await saveExposure('1')
  await saveExposure('0')
  expect(await page.evaluate(() => window.app?.graph.nodes.map(node => ({id: node.id, type: node.type})))).toEqual(graphBefore)
  await page.screenshot({path: fileURLToPath(new URL('browser-members.png', root)), fullPage: true})
  await workspace.getByRole('button', {name: '← 返回素材库', exact: true}).click()
  await expect(workspace.getByRole('tablist', {name: '素材用途'})).toBeVisible()
  await expect(workspace.locator('.apf-assets-table tbody tr').filter({hasText: groupName})).toHaveCount(1)
  expect(errors).toEqual([])
})


test('standalone summary retains its original-version content observation', async ({page, errors}) => {
  await page.goto('/')
  const workspace = page.locator('.apf-workspace')
  await workspace.getByRole('textbox',{name:'搜索',exact:true}).fill(standaloneName)
  const row = workspace.locator('.apf-assets-table tbody tr').filter({hasText: standaloneName})
  await expect(row).toHaveCount(1)
  await row.locator('td.apf-column-name').click({position: {x: 2, y: 2}})
  const inspect = workspace.getByRole('button', {name: '检查文件变化', exact: true})
  await expect(inspect).toBeVisible()
  const observed = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/content-observation'))
  await inspect.click()
  const response = await observed
  expect(response.status()).toBe(200)
  expect((await response.json()).state).toBe('unchanged')
  expect(errors).toEqual([])
  await page.screenshot({path: fileURLToPath(new URL('browser-standalone.png', root)), fullPage: true})
})

test('calibration editing explicitly reads all fixed members and retains an unsaved draft',async({page})=>{
  const writes:string[]=[],reads:string[]=[]
  page.on('request',request=>{
    const url=new URL(request.url())
    if(url.pathname.includes('/api/v1/')&&request.method()!=='GET')writes.push(request.method()+' '+url.pathname)
    if(url.pathname.endsWith('/datasets/'+datasetId))reads.push(request.url())
  })
  await page.goto('/')
  const workspace=page.locator('.apf-workspace')
  const group=workspace.locator('.apf-assets-table tbody tr').filter({hasText:groupName})
  await group.locator('.apf-member-open').click()
  const graphBefore=await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))
  const editor=workspace.locator('.apf-calibration-editor')
  const detail=page.waitForResponse(response=>response.request().method()==='GET'&&Boolean(new URL(response.url()).pathname.match(/\/datasets\/[^/]+\/versions\/[^/]+$/)))
  await editor.locator('summary').click()
  const fixed=zDatasetVersionOut.parse(await(await detail).json())
  expect(fixed.members).toHaveLength(52)
  expect(fixed.members.map(member=>member.position)).toEqual(Array.from({length:52},(_,index)=>index))
  await expect(editor.getByText('完整成员 52 张 · 校准关联保存作用于全部成员。',{exact:true})).toBeVisible()
  const name=editor.locator('#calibration-group-name')
  await name.fill('G5 unsaved calibration draft')
  const readsBefore=reads.length
  await page.waitForTimeout(11_000)
  await expect(name).toHaveValue('G5 unsaved calibration draft')
  expect(reads).toHaveLength(readsBefore)
  expect(writes).toEqual([])
  expect(await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))).toEqual(graphBefore)
})

test('current capabilities, node and package metadata match the generated contract',async({request})=>{
 const results=await Promise.all([
  request.get('/astrophotoflow/api/v1/capabilities'),
  request.get('/astrophotoflow/api/v1/nodes'),
  request.get('/astrophotoflow/api/v1/software/packages')
 ])
 for(const response of results)expect(response.status()).toBe(200)
 zServiceCapabilities.parse(await results[0].json())
 const nodes=z.array(zNodeCapability).parse(await results[1].json())
 const packages=z.array(zSoftwarePackage).parse(await results[2].json())
 expect(packages.some(item=>item.package_id==='siril')).toBe(true)
 expect(nodes.every(item=>typeof item.node.content_token==='string')).toBe(true)
})


async function standaloneAsset(request: APIRequestContext) {
  const response=await request.get('/astrophotoflow/api/v1/library/assets/'+standaloneId)
  expect(response.status()).toBe(200)
  return zAssetOut.parse(await response.json())
}

async function restoreSyntheticName(request: Parameters<typeof standaloneAsset>[0], id: string, name: string) {
  const response=await request.get('/astrophotoflow/api/v1/library/assets/'+id)
  expect(response.status()).toBe(200)
  const current=zAssetOut.parse(await response.json())
  const restored=await request.patch('/astrophotoflow/api/v1/library/assets/'+id,{data:{base_revision:current.revision,name}})
  expect(restored.status()).toBe(200)
}

test('discovers a synthetic metadata change made through another API entry',async({page,request})=>{
  const original=await standaloneAsset(request)
  const changed=original.name+' [G5 external change]'
  await page.goto('/')
  await page.locator('.apf-workspace').getByRole('textbox',{name:'搜索',exact:true}).fill(original.name)
  const row=page.locator('.apf-workspace .apf-assets-table tbody tr').filter({hasText:original.name})
  await expect(row).toHaveCount(1)
  try {
    const response=await request.patch('/astrophotoflow/api/v1/library/assets/'+original.id,{data:{base_revision:original.revision,name:changed}})
    expect(response.status()).toBe(200)
    await expect(row.locator('.apf-column-name')).toContainText(changed)
  } finally {await restoreSyntheticName(request,original.id,original.name)}
})

test('preserves a real inline draft and its original revision across a background refresh',async({page,request})=>{
  const original=await standaloneAsset(request)
  const changed=original.name+' [G5 concurrent change]', draft='G5 browser unsaved draft'
  await page.goto('/')
  const workspace=page.locator('.apf-workspace')
  await Promise.all([
    page.waitForResponse(response => response.request().method() === 'GET' && new URL(response.url()).pathname.endsWith('/library/items') && new URL(response.url()).searchParams.get('q') === original.name),
    workspace.getByRole('textbox',{name:'搜索',exact:true}).fill(original.name)
  ])
  const row=workspace.locator('.apf-assets-table tbody tr').filter({hasText:original.name})
  await expect(row).toHaveCount(1)
  const graphBefore=await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))
  await row.locator('.apf-column-name .apf-inline-value').dblclick()
  const input=workspace.locator('.apf-column-name input')
  await input.fill(draft)
  try {
    const refreshed=page.waitForResponse(async response=>{
      if(response.request().method()!=='GET'||!new URL(response.url()).pathname.endsWith('/library/items'))return false
      const items=zLibraryItemPage.parse(await response.json()).items
      return items.some(item=>item.id===original.id&&item.name===changed)
    })
    const response=await request.patch('/astrophotoflow/api/v1/library/assets/'+original.id,{data:{base_revision:original.revision,name:changed}})
    expect(response.status()).toBe(200)
    expect((await refreshed).status()).toBe(200)
    const editor=workspace.locator('.apf-column-name input')
    await expect(editor).toHaveValue(draft)
    const conflict=page.waitForResponse(response=>response.request().method()==='PATCH'&&new URL(response.url()).pathname.endsWith('/library/assets/'+original.id))
    await editor.press('Enter')
    const rejected=await conflict
    expect(rejected.status()).toBe(409)
    expect((await rejected.json()).error.code).toBe('REVISION_CONFLICT')
    await expect(editor).toHaveValue(draft)
    await editor.press('Escape')
    await expect(workspace.locator('.apf-column-name input')).toHaveCount(0)
    await expect(workspace.locator('.apf-assets-table tbody tr').filter({hasText:changed})).toHaveCount(1)
    expect(await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))).toEqual(graphBefore)
  } finally {await restoreSyntheticName(request,original.id,original.name)}
})

test('continues local library queries while the browser reports no internet connection',async({page})=>{
  await page.goto('/')
  const workspace=page.locator('.apf-workspace')
  await expect(workspace.locator('.apf-assets-table tbody tr').filter({hasText:groupName})).toHaveCount(1)
  await page.evaluate(()=>{
    Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>false})
    window.dispatchEvent(new Event('offline'))
  })
  const response=page.waitForResponse(response=>response.request().method()==='GET'&&new URL(response.url()).pathname.endsWith('/library/items')&&new URL(response.url()).searchParams.get('q')===standaloneName)
  await workspace.getByRole('textbox',{name:'搜索',exact:true}).fill(standaloneName)
  expect((await response).status()).toBe(200)
  await expect(workspace.locator('.apf-assets-table tbody tr').filter({hasText:standaloneName})).toHaveCount(1)
  expect(await page.evaluate(()=>navigator.onLine)).toBe(false)
})


test('mounts the native software sidebar against its real workspace without proposing an action',async({page})=>{
  const actions:string[]=[]
  page.on('request',request=>{
    const path=new URL(request.url()).pathname
    if(request.method()==='POST'&&path.includes('/software/')&&/\/(install|uninstall|prepare)$/.test(path))actions.push(path)
  })
  const health=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/health'))
  const details=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/software/packages/siril'))
  await page.goto('/#/workflows?apf_panel=software')
  const workspace=zServiceHealth.parse(await (await health).json()).workspace
  expect(workspace.replaceAll('\\','/').toLowerCase()).toBe(seed.workspace.replaceAll('\\','/').toLowerCase())
  expect(zSoftwarePackageDetails.parse(await (await details).json()).package.package_id).toBe('siril')
  const panel=page.getByTestId('software-panel')
  await expect(panel).toBeVisible()
  await expect(panel.getByTestId('software-package-row').filter({hasText:'Siril'})).toHaveCount(1)
  expect(actions).toEqual([])
})


test('native equipment editors create registered devices, a setup and a sparse zero-gain preset',async({page,request})=>{
  const created: {entry_type:'equipment'|'equipment_setup'|'capture_preset';id:string;path:string}[]=[]
  const suffix=String(Date.now())
  const rigName='G5 browser rig '+suffix
  const filterName='G5 browser filter '+suffix
  try{
    await page.goto('/')
    const workspace=page.locator('.apf-workspace')
    await page.waitForFunction(()=>Boolean(window.app?.graph))
    const graphBefore=await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))
    await workspace.getByRole('button',{name:'设备管理',exact:true}).click()
    await workspace.getByRole('button',{name:'新建设备组合',exact:true}).click()
    const setupForm=page.getByRole('form',{name:'设备组合表单',exact:true})
    await setupForm.locator('#setup-name').fill(rigName)
    await setupForm.getByRole('button',{name:'新建滤镜',exact:true}).click()
    const deviceForm=page.getByRole('form',{name:'新建设备表单',exact:true})
    await deviceForm.locator('#device-name').fill(filterName)
    const deviceResponse=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname.endsWith('/api/v1/equipment'))
    await deviceForm.getByRole('button',{name:'保存设备并加入',exact:true}).click()
    const savedDevice=await deviceResponse
    const device=zEquipmentPage.shape.items.element.parse(await savedDevice.json())
    created.push({entry_type:'equipment',id:device.id,path:'/equipment/'+device.id})
    expect(savedDevice.status()).toBe(201)
    await expect(setupForm).toBeVisible()
    await expect(setupForm.locator('#setup-name')).toHaveValue(rigName)
    const setupResponse=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname.endsWith('/api/v1/equipment-setups'))
    await setupForm.getByRole('button',{name:'保存设备组合',exact:true}).click()
    const savedSetup=await setupResponse
    const setup=zEquipmentSetupOut.parse(await savedSetup.json())
    created.push({entry_type:'equipment_setup',id:setup.id,path:'/equipment-setups/'+setup.id})
    expect(savedSetup.status()).toBe(201)
    expect(setup.components).toHaveLength(1)
    expect(setup.components[0]).toMatchObject({source:'registered',equipment_id:device.id})
    await workspace.getByRole('button',{name:'新建拍摄预设',exact:true}).click()
    const presetForm=page.getByRole('form',{name:'拍摄预设表单',exact:true})
    await presetForm.locator('#preset-name').fill('G5 zero')
    await presetForm.getByLabel('ISO／增益',{exact:true}).click()
    await page.getByRole('option',{name:'增益',exact:true}).click()
    await presetForm.getByRole('spinbutton',{name:'增益（Gain）',exact:true}).fill('0')
    await presetForm.getByLabel('预设滤镜',{exact:true}).click()
    await page.getByRole('option',{name:'不使用',exact:true}).click()
    const presetResponse=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname.endsWith('/equipment-setups/'+setup.id+'/presets'))
    await presetForm.getByRole('button',{name:'保存拍摄预设',exact:true}).click()
    const savedPreset=await presetResponse
    const preset=zCapturePresetOut.parse(await savedPreset.json())
    created.push({entry_type:'capture_preset',id:preset.id,path:'/capture-presets/'+preset.id})
    expect(savedPreset.status()).toBe(201)
    expect(preset.parameters.gain).toBe(0)
    expect(preset.equipment_selection).toEqual({filter:null})
    await expect(workspace.getByRole('button',{name:preset.name,exact:true})).toBeVisible()
    expect(await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))).toEqual(graphBefore)
  }finally{
    if(created.length){
      const items=[]
      for(const entry of created){
        const response=await request.get('/astrophotoflow/api/v1'+entry.path)
        expect(response.status()).toBe(200)
        const current=await response.json()
        items.push({entry_type:entry.entry_type,id:entry.id,revision:current.revision})
      }
      const response=await request.post('/astrophotoflow/api/v1/equipment-management/delete-preview',{data:{items}})
      expect(response.status()).toBe(200)
      const preview=zManagementTrashPreviewOut.parse(await response.json())
      expect(preview.blocked).toBe(false)
      const removed=await request.post('/astrophotoflow/api/v1/equipment-management/delete',{data:{items,preview_fingerprint:preview.preview_fingerprint}})
      expect(removed.status()).toBe(200)
      expect((await removed.json()).deleted_count).toBe(created.length)
    }
  }
})


test('real native websocket reconnection verifies identity before restoring an unsaved equipment draft',async({page})=>{
  await page.goto('/')
  const workspace=page.locator('.apf-workspace')
  await expect(workspace).toBeVisible()
  await page.waitForFunction(()=>window.app?.api.socket?.readyState===WebSocket.OPEN)
  await workspace.getByRole('button',{name:'设备管理',exact:true}).click()
  await workspace.getByRole('button',{name:'新建设备组合',exact:true}).click()
  const form=page.getByRole('form',{name:'设备组合表单',exact:true})
  const draft='G5 unsaved reconnect draft'
  await form.locator('#setup-name').fill(draft)
  const graphBefore=await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))
  const writes:string[]=[]
  page.on('request',request=>{
    if(new URL(request.url()).pathname.includes('/api/v1/')&&request.method()!=='GET')writes.push(request.method()+' '+new URL(request.url()).pathname)
  })
  let release!:()=>void
  const verification=new Promise<void>(resolve=>{release=resolve})
  await page.route('**/astrophotoflow/api/v1/health',async route=>{await verification;await route.continue()})
  try{
    const identityRead=page.waitForRequest(request=>new URL(request.url()).pathname.endsWith('/api/v1/health'))
    await page.evaluate(()=>{
      const socket=window.app?.api.socket
      if(!socket)throw new Error('Expected the active native websocket')
      socket.close(1000,'G5 isolated reconnection verification')
    })
    await identityRead
    await expect(form).toBeHidden()
    await expect(page.locator('.apf-workspace-connection')).toHaveAttribute('aria-busy','true')
    release()
    await expect(form).toBeVisible()
    await expect(form.locator('#setup-name')).toHaveValue(draft)
    expect(writes).toEqual([])
    expect(await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))).toEqual(graphBefore)
  }finally{release();await page.unroute('**/astrophotoflow/api/v1/health')}
})


test('native workbench settings read actual configuration and discard a draft without saving or restarting',async({page})=>{
  const writes:string[]=[]
  await page.route('**/astrophotoflow/api/v1/settings/workbench**',route=>{
    if(route.request().method()==='GET')return route.continue()
    writes.push(route.request().method()+' '+new URL(route.request().url()).pathname)
    return route.abort('blockedbyclient')
  })
  await page.goto('/')
  await page.waitForFunction(()=>Boolean(window.app?.graph))
  const graphBefore=await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))
  const response=page.waitForResponse(response=>response.request().method()==='GET'&&new URL(response.url()).pathname.endsWith('/settings/workbench'))
  await page.getByRole('button',{name:'设置 (Ctrl + ,)',exact:true}).click()
  await page.getByText('工作台',{exact:true}).first().click()
  const config=zConfigState.parse(await(await response).json())
  expect(config.config_path.replaceAll('\\','/').toLowerCase()).toBe(seed.workspace.replaceAll('\\','/').toLowerCase()+'/config.toml')
  const panel=page.getByTestId('workbench-settings')
  await expect(panel).toBeVisible()
  const workers=panel.locator('#file_workers')
  await expect(workers).toHaveValue(String(config.saved.file_workers))
  await workers.fill(String(config.saved.file_workers+1))
  await workers.press('Tab')
  await expect(panel.getByTestId('workbench-restart')).toBeDisabled()
  const read=page.waitForResponse(response=>response.request().method()==='GET'&&new URL(response.url()).pathname.endsWith('/settings/workbench'))
  await panel.getByRole('button',{name:'重新读取配置',exact:true}).click()
  expect((await read).status()).toBe(200)
  await expect(workers).toHaveValue(String(config.saved.file_workers))
  expect(writes).toEqual([])
  expect(await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))).toEqual(graphBefore)
})


test('a real native result widget reads its mocked call record using the shared Query provider',async({page})=>{
  const prompt='89123456-1111-4111-8111-111111111111',call='98234567-2222-4222-8222-222222222222'
  const queued:string[]=[]
  await page.route('**/prompt',route=>{queued.push(route.request().method());return route.abort('blockedbyclient')})
  let reply:ReturnType<typeof zSoftwareCallResult.parse>|undefined
  await page.route('**/astrophotoflow/api/v1/runs/'+prompt+'/calls/'+call,route=>{
    if(!reply)return route.abort('blockedbyclient')
    return route.fulfill({status:200,json:reply})
  })
  await page.goto('/')
  await page.waitForFunction(()=>Boolean(window.app?.graph))
  await expect(page.locator('.apf-workspace')).toBeVisible()
  await page.waitForFunction(()=>Object.keys(window.LiteGraph?.registered_node_types??{}).some(name=>/^APF_[a-f0-9]{32}$/.test(name)))
  const before=await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))
  const created=await page.evaluate(()=>{
    const name=Object.keys(window.LiteGraph.registered_node_types).find(name=>/^APF_[a-f0-9]{32}$/.test(name))!
    const node=window.LiteGraph.createNode(name)!
    node.properties.apfAutomaticResult=false
    node.pos=[350,160]
    window.app!.graph.add(node)
    window.app!.canvas.setDirty(true,true)
    return {id:String(node.id),workflowId:window.app!.graph.rootGraph.id}
  })
  try{
    reply=zSoftwareCallResult.parse({log_url: `/astrophotoflow/api/v1/runs/${prompt}/calls/${call}/log`, prompt_id:prompt,call_id:call,node_id:created.id,workflow_id:created.workflowId,calculation_signature:null,
      package_id:'siril',software_version:'1.4.4',bundle_version:null,bundle_commit:null,development_source:null,operation_id:null,
      definition_token:null,state:'completed',ports:[],preview_error:null,observation:null,error:null})
    const read=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/runs/'+prompt+'/calls/'+call))
    await page.evaluate(({nodeId,reply})=>{window.app!.nodeOutputs[nodeId]={apf_result:[reply]};window.app!.canvas.setDirty(true,true)},{nodeId:created.id,reply})
    expect((await read).status()).toBe(200)
    await expect(page.getByText(/89123456/).first()).toBeVisible()
    expect(queued).toEqual([])
  }finally{
    await page.evaluate(nodeId=>{
      const node=window.app!.graph.nodes.find(node=>String(node.id)===nodeId)
      if(node)window.app!.graph.remove(node)
      delete window.app!.nodeOutputs[nodeId]
    },created.id)
  }
  expect(await page.evaluate(()=>window.app?.graph.nodes.map(node=>({id:node.id,type:node.type})))).toEqual(before)
})

test('local library queries remain active when the browser online flag reports offline',async({page,errors})=>{
 void errors
 await page.addInitScript(()=>Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>false}))
 await page.goto('/')
 const workspace=page.locator('.apf-workspace');await expect(workspace).toBeVisible()
 await page.evaluate(()=>window.dispatchEvent(new Event('offline')))
 expect(await page.evaluate(()=>navigator.onLine)).toBe(false)
 const read=page.waitForResponse(response=>{
  const url=new URL(response.url())
  return response.request().method()==='GET'&&url.pathname.endsWith('/library/items')&&[...url.searchParams.values()].includes(groupName)
 })
 await workspace.getByRole('textbox',{name:'搜索',exact:true}).fill(groupName)
 const response=await read
 expect(response.status()).toBe(200)
 const body=zLibraryItemPage.parse(await response.json())
 expect(body.items.some(item=>item.id===datasetId)).toBe(true)
 await expect(workspace.locator('.apf-assets-table tbody tr').filter({hasText:groupName})).toHaveCount(1)
})
