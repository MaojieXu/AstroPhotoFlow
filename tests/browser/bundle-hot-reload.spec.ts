import { execFile } from 'node:child_process'
import { copyFile, readFile, rename, writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { join, resolve } from 'node:path'
import { promisify } from 'node:util'

import { expect, openSidebar, test } from './native.fixtures'
import { createSyntheticAsset } from './scientificAssets'
import { zSoftwareCallResult } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'

const run = promisify(execFile)
const source = process.env.APF_TEST_SIRIL_BUNDLE
const python = process.env.APF_TEST_BUNDLE_PYTHON
test.skip(!source || !python, 'Select a prepared Siril checkout and the development Python interpreter.')

test('an open workbench adopts Bundle sources, Python edits and new node definitions', async ({
  isolatedWorkspace, page, request
}) => {
  test.setTimeout(180_000)
  const api = '/astrophotoflow/api/v1'
  const type = 'APF_169de0837f814cdea3295541ecacf463'
  const session = 'bundle-test-' + randomUUID()
  const directory = join(isolatedWorkspace, session)
  const staging = join(isolatedWorkspace, session + '-checkout')
  const checkout = join(directory, 'siril')
  const retired = join(isolatedWorkspace, session + '-retired')
  const processes = join(isolatedWorkspace, 'run', 'processes.json')
  const originalProcesses = await readFile(processes, 'utf8')
  const configure = (root?: string) => run(python!, ['-c', [
    'import sys',
    'from pathlib import Path',
    'from astrophotoflow.modules.software import development',
    'workspace = Path(sys.argv[1])',
    'root = Path(sys.argv[2]) if len(sys.argv) > 2 else None',
    'development.configure(workspace, [], [], sys.executable, repository=root, clear_repository=root is None)'
  ].join('\n'), isolatedWorkspace, ...(root ? [root] : [])])
  await configure(directory)
  await page.goto('/')
  await page.waitForFunction(() => window.app?.isGraphReady)
  const pageStarted = await page.evaluate(() => performance.timeOrigin)
  expect(await page.evaluate(type => Boolean(window.LiteGraph.registered_node_types[type]), type)).toBe(false)

  await run('git', ['clone', '--quiet', '--no-hardlinks', '--', resolve(source!), staging])
  const config = join(staging, 'development.json')
  await copyFile(join(source!, 'development.json'), config)
  await copyFile(join(source!, 'adapter', 'planning', 'build.py'), join(staging, 'adapter', 'planning', 'build.py'))
  const development = JSON.parse(await readFile(config, 'utf8'))
  expect(development.watch).toContain('adapter/recipes/**/*.py')
  const adapter = join(staging, 'adapter', 'siril.py')
  await writeFile(adapter, (await readFile(adapter, 'utf8')) + [
    '',
    'from .hot_reload_probe import target_bg',
    '_build_plan = build_plan',
    'def build_plan(operation_id, sources, parameters, directory, **options):',
    '    if operation_id == "autostretch":',
    '        parameters = {**parameters, "targetbg": target_bg}',
    '    plan = _build_plan(operation_id, sources, parameters, directory, **options)',
    '    return plan',
    ''
  ].join('\n'))
  await writeFile(join(staging, 'adapter', 'hot_reload_probe.py'), 'target_bg = 0.25\n')
  await rename(staging, checkout)
  try {
    await openSidebar(page, 'software')
    const developmentRow = page.getByTestId('development-source').filter({ hasText: checkout })
    await expect(developmentRow).toBeVisible()
    await expect(developmentRow).toContainText('就绪')
    await page.waitForFunction(type => Boolean(window.LiteGraph.registered_node_types[type]), type)

    const asset = await createSyntheticAsset(request, session)
    const reference = JSON.stringify({
      kind: 'asset', asset_id: asset.id,
      selection: { kind: 'whole_file' }
    })
    const oldId = await page.evaluate(({ type, reference }) => {
      const graph = window.app.graph
      graph.clear()
      const input = window.LiteGraph.createNode('APF_DATA_REFERENCE')
      const tool = window.LiteGraph.createNode(type)
      input.pos = [390, 180]
      tool.pos = [780, 180]
      input.widgets.find(widget => widget.name === 'reference').value = reference
      tool.properties.apfAutomaticResult = false
      graph.add(input)
      graph.add(tool)
      input.connect(0, tool, 0)
      return tool.id
    }, { type, reference })
    const execute = async () => {
      const [queued, submitted] = await Promise.all([
        page.waitForResponse(response => response.request().method() === 'POST' &&
          new URL(response.url()).pathname.endsWith('/prompt'), { timeout: 12_000 }),
        page.evaluate(() => window.app.queuePrompt(0, 1)).then(result => {
          expect(result, 'The current Bundle instance must be eligible to run').toBe(true)
          return result
        })
      ])
      expect(submitted && queued.ok()).toBe(true)
      const { prompt_id } = await queued.json()
      let call: ReturnType<typeof zSoftwareCallResult.parse> | undefined
      await expect.poll(async () => {
        const response = await request.get(api + '/runs/' + prompt_id + '/calls')
        expect(response.ok()).toBe(true)
        const calls = zSoftwareCallResult.array().parse(await response.json())
        call = calls.find(item => item.node_id === String(oldId))
        return call && !['starting', 'running'].includes(call.state)
      }, { timeout: 30_000 }).toBe(true)
      expect(call!.state, call!.error?.message).toBe('completed')
      const output = join(isolatedWorkspace, 'runs', prompt_id, 'work', call!.call_id, 'member-000000', 'result.fit')
      const pixels = await run(python!, ['-c',
        'import sys, numpy as np; from astropy.io import fits; print(float(np.median(fits.getdata(sys.argv[1]))))', output])
      return Number(pixels.stdout.trim())
    }
    const before = await execute()
    const beforeSource = await developmentRow.textContent()
    const helper = join(checkout, 'adapter', 'hot_reload_probe.py')
    const generationLog = join(isolatedWorkspace, 'logs', 'bundle-development-siril.log')
    const generation = await readFile(generationLog)
    await writeFile(helper, 'target_bg = 0.40\n')
    await expect(developmentRow).not.toHaveText(beforeSource!)
    await expect(developmentRow).toContainText('就绪')
    expect(await execute()).not.toBeCloseTo(before, 4)
    expect(await readFile(generationLog)).toEqual(generation)

    const recipes = join(checkout, 'adapter', 'recipes', 'catalog.py')
    const original = await readFile(recipes, 'utf8')
    const changed = original.replace("number('targetbg', 0.25, minimum=0, maximum=1)", "number('targetbg', 0.32, minimum=0, maximum=1)")
    expect(changed).not.toBe(original)
    const oldGraph = await page.evaluate(() => window.app.graph.serialize())
    await writeFile(recipes, changed)
    await expect(page.getByText('定义已更新，请重新添加节点。', { exact: true }).first()).toBeVisible()
    expect(await page.evaluate(() => window.app.queuePrompt(0, 1))).toBe(false)
    const graph = await page.evaluate(() => window.app.graph.serialize())
    expect(graph.nodes).toEqual(oldGraph.nodes)
    expect(graph.links).toEqual(oldGraph.links)
    expect(await page.evaluate(type => window.LiteGraph.createNode(type)
      .widgets.find(widget => widget.name === 'targetbg').value, type)).toBe(0.32)

    await writeFile(helper, 'target_bg =\n')
    await expect(developmentRow.getByRole('alert')).toContainText('hot_reload_probe.py')
    await writeFile(helper, 'target_bg = 0.40\n')
    await expect(developmentRow.getByRole('alert')).toHaveCount(0)
    await expect(developmentRow).toContainText('已就绪')
    await rename(checkout, retired)
    await expect(developmentRow).toHaveCount(0)
    await page.waitForFunction(type => !window.LiteGraph.registered_node_types[type], type)
    expect(await readFile(processes, 'utf8')).toBe(originalProcesses)
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(pageStarted)
    expect(await page.evaluate(id => Boolean(window.app.graph.getNodeById(id)), oldId)).toBe(true)
  } finally {
    await configure()
  }
})
