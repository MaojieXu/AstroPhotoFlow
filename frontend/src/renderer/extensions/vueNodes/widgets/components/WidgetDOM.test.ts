import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { fromPartial } from '@total-typescript/shoehorn'
import { render, screen } from '@testing-library/vue'
import { defineComponent, nextTick } from 'vue'
import type { ComponentWidget } from '@/scripts/domWidget'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const resolveMock = vi.hoisted(() => vi.fn())
vi.mock(
  import('@/renderer/extensions/vueNodes/widgets/utils/resolvePromotedWidget'),
  () => ({
    resolveWidgetFromHostNode: resolveMock
  })
)

const isDOMWidgetMock = vi.hoisted(() => vi.fn(() => true))
const isComponentWidgetMock = vi.hoisted(() => vi.fn(() => false))
vi.mock<unknown>(import('@/scripts/domWidget'), () => ({
  isDOMWidget: isDOMWidgetMock,
  isComponentWidget: isComponentWidgetMock
}))

import { toNodeId } from '@/types/nodeId'

import WidgetDOM from './WidgetDOM.vue'
import { createMockWidget } from './widgetTestUtils'

beforeEach(() => {
  useCanvasStore().canvas = fromPartial({
    canvas: document.createElement('canvas'),
    graph: { getNodeById: vi.fn(() => null) }
  })
})

describe('WidgetDOM', () => {
  beforeEach(() => {
    isDOMWidgetMock.mockReturnValue(true)
    isComponentWidgetMock.mockReturnValue(false)
  })

  function mountWithWidget(domElement: HTMLElement | null) {
    if (domElement) {
      vi.mocked(
        useCanvasStore().getCanvas().graph!.getNodeById
      ).mockReturnValue(new LGraphNode('test'))
      resolveMock.mockReturnValue({
        node: { mock: true },
        widget: { element: domElement, name: 'dom' }
      })
    }
    return render(WidgetDOM, {
      props: {
        widget: createMockWidget<undefined>({
          value: undefined,
          name: 'dom',
          type: 'dom'
        }),
        nodeId: toNodeId('n1')
      }
    })
  }

  it('mounts a native Vue ComponentWidget in Nodes 2.0 without a second app', async () => {
    const node = new LGraphNode('Data')
    vi.mocked(useCanvasStore().getCanvas().graph!.getNodeById).mockReturnValue(node)
    const widget = fromPartial<ComponentWidget<string>>({
      node, name: 'display', value: '', options: { surfaces: { canvas: 'never', vueNode: 'shown', panel: 'never' } },
      component: defineComponent({ template: '<span>Scientific image preview</span>' }),
      computeLayoutSize: () => ({ minHeight: 440 })
    })
    resolveMock.mockReturnValue({ node, widget })
    isDOMWidgetMock.mockReturnValue(false)
    isComponentWidgetMock.mockReturnValue(true)
    render(WidgetDOM, { props: { widget: createMockWidget<undefined>({ value: undefined, name: 'display', type: 'custom' }), nodeId: toNodeId('n1') } })
    await nextTick()
    expect(screen.getByText('Scientific image preview')).toBeInTheDocument()
  })

  it('leaves existing canvas-backed ComponentWidgets on their original overlay path', () => {
    const node = new LGraphNode('Existing component')
    vi.mocked(useCanvasStore().getCanvas().graph!.getNodeById).mockReturnValue(node)
    const widget = fromPartial<ComponentWidget<string>>({ node, name: 'existing', value: '', options: {}, component: defineComponent({ template: '<span>Existing overlay component</span>' }) })
    resolveMock.mockReturnValue({ node, widget })
    isDOMWidgetMock.mockReturnValue(false)
    isComponentWidgetMock.mockReturnValue(true)
    render(WidgetDOM, { props: { widget: createMockWidget<undefined>({ value: undefined, name: 'existing', type: 'custom' }), nodeId: toNodeId('n1') } })
    expect(screen.queryByText('Existing overlay component')).not.toBeInTheDocument()
  })

  it('mounts the resolved DOM widget element inside the container', () => {
    const hosted = document.createElement('div')
    hosted.setAttribute('data-testid', 'hosted-dom')
    hosted.textContent = 'hosted content'

    const { container } = mountWithWidget(hosted)

    // oxlint-disable-next-line testing-library/no-container, testing-library/no-node-access
    expect(container.querySelector('[data-testid="hosted-dom"]')).toBe(hosted)
  })

  it('renders an empty container when no host node is found', () => {
    vi.mocked(useCanvasStore().getCanvas().graph!.getNodeById).mockReturnValue(
      null
    )
    resolveMock.mockReturnValue(undefined)

    const { container } = render(WidgetDOM, {
      props: {
        widget: createMockWidget<undefined>({
          value: undefined,
          name: 'dom',
          type: 'dom'
        }),
        nodeId: toNodeId('missing')
      }
    })

    // oxlint-disable-next-line testing-library/no-node-access
    const root = container.firstElementChild as HTMLElement
    expect(root).toBeInTheDocument()
    // oxlint-disable-next-line testing-library/no-node-access
    expect(root.children).toHaveLength(0)
  })

  it('skips mounting when the resolved widget is not a DOM widget', () => {
    const hosted = document.createElement('div')
    hosted.setAttribute('data-testid', 'hosted-dom')

    vi.mocked(useCanvasStore().getCanvas().graph!.getNodeById).mockReturnValue(
      new LGraphNode('test')
    )
    resolveMock.mockReturnValue({
      node: { mock: true },
      widget: { element: hosted, name: 'dom' }
    })
    isDOMWidgetMock.mockReturnValue(false)

    const { container } = render(WidgetDOM, {
      props: {
        widget: createMockWidget<undefined>({
          value: undefined,
          name: 'dom',
          type: 'dom'
        }),
        nodeId: toNodeId('n1')
      }
    })

    // oxlint-disable-next-line testing-library/no-container, testing-library/no-node-access
    expect(container.querySelector('[data-testid="hosted-dom"]')).toBeNull()
  })

  it('renders a visible root element for pointer-event capture', () => {
    const { container } = mountWithWidget(document.createElement('span'))
    // oxlint-disable-next-line testing-library/no-node-access
    const root = container.firstElementChild as HTMLElement
    expect(root).toBeVisible()
  })
})
