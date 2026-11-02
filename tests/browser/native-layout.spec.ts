import { test, expect } from './native.fixtures'

for (const width of [1280, 900]) {
  test(`library and equipment keep a common left boundary at ${width}px`, async ({
    page
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    const workspace = page.locator('.apf-workspace')
    await expect(workspace).toBeVisible()
    const library = await workspace.locator('.apf-main').boundingBox()
    await workspace
      .getByRole('button', { name: '设备管理', exact: true })
      .click()
    const equipment = await workspace.locator('.apf-main').boundingBox()
    expect(library).not.toBeNull()
    expect(equipment).not.toBeNull()
    expect(Math.abs(library!.x - equipment!.x)).toBeLessThanOrEqual(1)
    expect(Math.abs(library!.width - equipment!.width)).toBeLessThanOrEqual(1)
    for (const label of ['设备组合', '我的设备']) {
      const tab = workspace.getByRole('tab', { name: label, exact: true })
      await tab.click()
      await expect(tab).toHaveAttribute('data-state', 'active')
      const tabs = await workspace.locator('.apf-management-tabs').boundingBox()
      const first = await workspace
        .getByRole('tab', { name: '设备组合', exact: true })
        .boundingBox()
      expect(tabs).not.toBeNull()
      expect(first).not.toBeNull()
      expect(Math.abs(tabs!.x - first!.x)).toBeLessThanOrEqual(4)
    }
    await test
      .info()
      .attach('layout', {
        body: await page.screenshot(),
        contentType: 'image/png'
      })
  })
}
