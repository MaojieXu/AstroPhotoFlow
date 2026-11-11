import { execFile } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { unlink, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { promisify } from 'node:util'

import { test, expect, openSidebar } from './native.fixtures'
import { zNodesApiV1NodesGetResponse } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import type { NodeCapability } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/types.gen'

const run = promisify(execFile)
const python = process.env.APF_TEST_BUNDLE_PYTHON
const createdFiles: string[] = []
test.skip(!python, 'Select the development Python interpreter and a prepared Siril workspace.')
test.afterEach(async () => {
  for (const file of createdFiles.splice(0)) {
    await unlink(file).catch(error => { if (error.code !== 'ENOENT') throw error })
  }
})

test('Bundle and custom nodes follow the system language and adopt live translation edits', async ({
  page, request, isolatedWorkspace
}) => {
  let base: NodeCapability | undefined
  await expect.poll(async () => {
    const response = await request.get('/astrophotoflow/api/v1/nodes')
    expect(response.ok()).toBe(true)
    const capabilities = zNodesApiV1NodesGetResponse.parse(await response.json())
    base = capabilities.find(item => item.node.definition.source === 'package' &&
      item.node.definition.execution.operation_id === 'autostretch')
    return base?.available
  }, { message: 'Wait for Siril to finish registering its nodes' }).toBe(true)
  const definition = structuredClone(base!.node.definition)
  definition.definition_id = randomUUID()
  definition.source = 'custom'
  definition.name = 'Authored node'
  definition.description = 'Authored description'
  definition.category = ['localization-test']
  definition.inputs[0].name = 'photo'
  definition.outputs[0].name = 'final'
  definition.execution.inputs.image = 'photo'
  definition.execution.outputs = { final: 'image' }
  definition.parameters.find(item => item.name === 'targetbg')!.name = 'strength'
  definition.execution.parameters.targetbg = { kind: 'parameter', name: 'strength' }
  definition.localizations = {
    en: { name: 'My processing', category: ['My tools'], help: 'English help',
      inputs: { photo: { label: 'My input' } }, parameters: { strength: { label: 'My strength' } } },
    zh: { name: '自定义处理 @ 50%', category: ['我的工具'], help: '中文帮助',
      inputs: { photo: { label: '我的输入' } }, parameters: { strength: { label: '我的强度' } } }
  }
  const file = join(isolatedWorkspace, 'localization-' + definition.definition_id + '.json')
  createdFiles.push(file, join(isolatedWorkspace, 'nodes', definition.definition_id + '.json'))
  const type = 'APF_' + definition.definition_id.replaceAll('-', '')
  const publish = async (create: boolean) => {
    await writeFile(file, JSON.stringify(definition))
    await run(python!, ['-c', [
      'import sys', 'from pathlib import Path',
      'from astrophotoflow.contracts.nodes import NodeDefinition',
      'from astrophotoflow.core.config import load_running_settings',
      'from astrophotoflow.modules.nodes import public',
      'from astrophotoflow.modules.software.public import get_operation',
      'workspace = Path(sys.argv[1])',
      'settings = load_running_settings(workspace)',
      'definition = NodeDefinition.model_validate_json(Path(sys.argv[2]).read_text())',
      `operation = get_operation(settings, 'siril', '${base!.operation!.version}', 'autostretch')`,
      create ? 'public.create_definition(workspace, definition, operation)' :
        'public.update_definition(workspace, public.preview_definition_update(workspace, definition, public.get_definition(workspace, definition.definition_id).content_token, operation))'
    ].join('\n'), isolatedWorkspace, file], { env: { ...process.env, PYTHONUTF8: '1' } })
  }
  await page.goto('/')
  await expect(page.locator('#graph-canvas')).toBeVisible()
  await openSidebar(page, 'node-library')
  const search = page.getByRole('combobox')
  await search.fill('autostretch')
  await expect(page.getByRole('treeitem').filter({ hasText: base!.display!.zh!.name })).toBeVisible()
  await publish(true)
  await search.fill('自定义处理')
  await page.getByRole('treeitem', { name: 'siril', exact: true }).press('ArrowRight')
  await page.getByRole('treeitem', { name: '我的工具', exact: true }).press('ArrowRight')
  await expect(page.getByRole('treeitem').filter({ hasText: '自定义处理 @ 50%' })).toBeVisible()
  await page.waitForFunction(type => Boolean(window.LiteGraph.registered_node_types[type]), type)
  const ids = await page.evaluate(type => {
    const graph = window.app.graph
    graph.beforeChange()
    const node = window.LiteGraph.createNode(type)
    node.pos = [650, 200]
    node.properties.apfAutomaticResult = false
    node.widgets.find(widget => widget.name === 'strength').value = 0.37
    graph.add(node)
    const authored = window.LiteGraph.createNode(type)
    authored.pos = [1000, 200]
    authored.title = 'My retained title'
    authored.properties.apfAutomaticResult = false
    graph.add(authored)
    node.connect(0, authored, 0)
    graph.afterChange()
    graph.change()
    return [node.id, authored.id]
  }, type)
  await expect(page.getByTestId('node-header-' + ids[0])).toContainText('自定义处理 @ 50%')
  await expect(page.getByTestId('node-header-' + ids[1])).toContainText('My retained title')
  await expect(page.getByText('我的输入', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('我的强度', { exact: true }).first()).toBeVisible()
  const before = await page.evaluate(() => window.app.graph.serialize())
  definition.localizations.zh!.name = '热更新节点'
  definition.localizations.zh!.parameters!.strength.label = '热更新强度'
  await publish(false)
  await search.fill('热更新节点')
  await page.getByRole('treeitem', { name: 'siril', exact: true }).press('ArrowRight')
  await page.getByRole('treeitem', { name: '我的工具', exact: true }).press('ArrowRight')
  await expect(page.getByRole('treeitem').filter({ hasText: '热更新节点' })).toBeVisible()
  await expect(page.getByTestId('node-header-' + ids[0])).toContainText('热更新节点')
  await expect(page.getByText('热更新强度', { exact: true }).first()).toBeVisible()
  await page.evaluate(() => window.app.ui.settings.setSettingValueAsync('Comfy.Locale', 'en'))
  await expect(page.getByTestId('node-header-' + ids[0])).toContainText('My processing')
  await expect(page.getByTestId('node-header-' + ids[1])).toContainText('My retained title')
  await page.evaluate(() => window.app.ui.settings.setSettingValueAsync('Comfy.Locale', 'zh'))
  await expect(page.getByTestId('node-header-' + ids[0])).toContainText('热更新节点')
  const after = await page.evaluate(() => window.app.graph.serialize())
  expect(after.links).toEqual(before.links)
  expect(after.nodes.map(node => node.widgets_values)).toEqual(before.nodes.map(node => node.widgets_values))
  await page.screenshot({ path: join(process.env.APF_BROWSER_REPORT!, 'node-localizations.png') })
})
