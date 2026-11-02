import userEvent from '@testing-library/user-event'
import { fireEvent, render, screen } from '@testing-library/vue'
import { fromPartial } from '@total-typescript/shoehorn'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'

import type { CanvasDataRequest } from '@astrophotoflow/ui'
import { useNodeDragToCanvas } from '@/composables/node/useNodeDragToCanvas'
import type { LGraphCanvas } from '@/lib/litegraph/src/litegraph'
import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import type { ComfyNodeDefImpl } from '@/stores/nodeDefStore'

import LibraryCanvasSource from './LibraryCanvasSource.vue'
import { addLibraryDataToCanvas } from './dataBridge'

const definition = vi.hoisted(() => ({ name: 'APF_DATA_REFERENCE' }))
vi.mock('@/stores/nodeDefStore', () => ({
  useNodeDefStore: () => ({
    nodeDefsByName: { APF_DATA_REFERENCE: definition }
  })
}))
vi.mock('@/components/node/NodePreviewCard.vue', () => ({
  default: { template: '<div />' }
}))
vi.mock('./dataBridge', () => ({ addLibraryDataToCanvas: vi.fn() }))

const source: CanvasDataRequest = {
  entry_type: 'asset',
  id: '00000000-0000-4000-8000-000000000001',
  version_id: '00000000-0000-4000-8000-000000000002'
}

beforeEach(() => {
  const element = document.createElement('canvas')
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(100, 100, 500, 500)
  )
  useCanvasStore().canvas = fromPartial<LGraphCanvas>({
    canvas: element,
    convertEventToCanvasOffset: () => [40, 60]
  })
})

afterEach(() => useNodeDragToCanvas().cancelDrag())

function renderSource(selected: CanvasDataRequest | undefined = source) {
  return render(LibraryCanvasSource, {
    props: { source: selected },
    slots: { default: '<button>Science frame</button>' }
  })
}

function renderRow() {
  const select = vi.fn()
  render(
    defineComponent({
      components: { LibraryCanvasSource },
      setup: () => ({ source, select }),
      template: `<table><tbody><LibraryCanvasSource as="tr" :source="source" click-target=".material-name" aria-selected="true" @click="select">
      <td><button class="material-name">Science frame</button><small>Original ready</small></td>
      <td><button>180 s</button><input aria-label="Edit exposure" value="180" /></td>
    </LibraryCanvasSource></tbody></table>`
    })
  )
  return select
}

describe('native library node placement', () => {
  it('cancels name placement before the second pointerup of a real double click', async () => {
    renderRow()
    const button = screen.getByRole('button', { name: 'Science frame' })
    // Sidebar content overlaps the native canvas rectangle; document capture
    // sees the second pointerup before the later dblclick event.
    for (const detail of [1, 2]) {
      await fireEvent.pointerDown(button, { clientX: 200, clientY: 200 })
      await fireEvent.mouseDown(button, { detail, clientX: 200, clientY: 200 })
      await fireEvent.pointerUp(button, { clientX: 200, clientY: 200 })
      await fireEvent.mouseUp(button, { detail, clientX: 200, clientY: 200 })
      await fireEvent.click(button, { detail })
    }
    await fireEvent.doubleClick(button)
    expect(addLibraryDataToCanvas).not.toHaveBeenCalled()
    expect(useNodeDragToCanvas().isDragging.value).toBe(false)
  })

  it.each(['Original ready', '180 s'])(
    'drags a row from %s and inserts the fixed source once',
    async (label) => {
      renderRow()
      const target = screen.getByText(label)
      expect(screen.getByRole('row')).toHaveAttribute('draggable', 'true')
      expect(screen.getByRole('row')).toHaveAttribute('aria-selected', 'true')
      await fireEvent.dragStart(target)
      await fireEvent(
        target,
        new MouseEvent('dragend', { bubbles: true, clientX: 200, clientY: 200 })
      )
      expect(addLibraryDataToCanvas).toHaveBeenCalledExactlyOnceWith(
        source,
        [40, 60]
      )
    }
  )

  it('drags from the row background without a text or image handle', async () => {
    renderRow()
    const row = screen.getByRole('row')
    await fireEvent.dragStart(row)
    await fireEvent(
      row,
      new MouseEvent('dragend', { bubbles: true, clientX: 200, clientY: 200 })
    )
    expect(addLibraryDataToCanvas).toHaveBeenCalledExactlyOnceWith(
      source,
      [40, 60]
    )
  })

  it('preserves row selection and starts click placement only from the name', async () => {
    const select = renderRow()
    await userEvent.click(screen.getByText('Original ready'))
    expect(select).toHaveBeenCalledTimes(1)
    expect(useNodeDragToCanvas().isDragging.value).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Science frame' }))
    expect(select).toHaveBeenCalledTimes(1)
    await fireEvent.pointerUp(document, { clientX: 200, clientY: 200 })
    expect(addLibraryDataToCanvas).toHaveBeenCalledExactlyOnceWith(
      source,
      [40, 60]
    )
  })

  it('does not start material placement when dragging inside an editor', async () => {
    renderRow()
    const editor = screen.getByRole('textbox', { name: 'Edit exposure' })
    await fireEvent.dragStart(editor)
    await fireEvent(
      editor,
      new MouseEvent('dragend', { bubbles: true, clientX: 200, clientY: 200 })
    )
    expect(useNodeDragToCanvas().isDragging.value).toBe(false)
    expect(addLibraryDataToCanvas).not.toHaveBeenCalled()
  })

  it('arms the native preview on click and prepares only at the chosen canvas position', async () => {
    renderSource()
    await userEvent.click(screen.getByRole('button', { name: 'Science frame' }))
    expect(useNodeDragToCanvas().draggedNode.value).toEqual(
      fromPartial<ComfyNodeDefImpl>(definition)
    )
    expect(addLibraryDataToCanvas).not.toHaveBeenCalled()
    await fireEvent.pointerUp(document, { clientX: 200, clientY: 200 })
    expect(addLibraryDataToCanvas).toHaveBeenCalledExactlyOnceWith(
      source,
      [40, 60]
    )
    expect(useNodeDragToCanvas().isDragging.value).toBe(false)
  })

  it('uses native drag and drop with the same fixed source', async () => {
    renderSource()
    const button = screen.getByRole('button', { name: 'Science frame' })
    await fireEvent.dragStart(button)
    expect(useNodeDragToCanvas().isDragging.value).toBe(true)
    expect(addLibraryDataToCanvas).not.toHaveBeenCalled()
    await fireEvent(
      button,
      new MouseEvent('dragend', { bubbles: true, clientX: 200, clientY: 200 })
    )
    expect(addLibraryDataToCanvas).toHaveBeenCalledExactlyOnceWith(
      source,
      [40, 60]
    )
    expect(useNodeDragToCanvas().isDragging.value).toBe(false)
  })

  it.each(['escape', 'outside', 'doubleclick'] as const)(
    'cancels %s without preparing data',
    async (reason) => {
      renderSource()
      const button = screen.getByRole('button', { name: 'Science frame' })
      await fireEvent.click(button)
      if (reason === 'escape')
        await fireEvent.keyDown(document, { key: 'Escape' })
      else if (reason === 'outside')
        await fireEvent.pointerUp(document, { clientX: 10, clientY: 10 })
      else await fireEvent.doubleClick(button)
      await fireEvent.pointerUp(document, { clientX: 200, clientY: 200 })
      expect(addLibraryDataToCanvas).not.toHaveBeenCalled()
      expect(useNodeDragToCanvas().isDragging.value).toBe(false)
    }
  )

  it('keeps the source selected at drag start when the list receives a newer version', async () => {
    const selected = ref(source)
    render(
      defineComponent({
        components: { LibraryCanvasSource },
        setup: () => ({ selected }),
        template:
          '<LibraryCanvasSource :source="selected"><button>Science frame</button></LibraryCanvasSource>'
      })
    )
    const button = screen.getByRole('button', { name: 'Science frame' })
    await fireEvent.dragStart(button)
    selected.value = {
      ...source,
      version_id: '00000000-0000-4000-8000-000000000003'
    }
    await fireEvent(
      button,
      new MouseEvent('dragend', { bubbles: true, clientX: 200, clientY: 200 })
    )
    expect(addLibraryDataToCanvas).toHaveBeenCalledExactlyOnceWith(
      source,
      [40, 60]
    )
  })

  it('does not arm or drag unavailable data', async () => {
    render(LibraryCanvasSource, {
      slots: { default: '<button>Unavailable frame</button>' }
    })
    const button = screen.getByRole('button', { name: 'Unavailable frame' })
    await fireEvent.click(button)
    await fireEvent.dragStart(button)
    await fireEvent.dragEnd(button, { clientX: 200, clientY: 200 })
    expect(addLibraryDataToCanvas).not.toHaveBeenCalled()
    expect(useNodeDragToCanvas().isDragging.value).toBe(false)
  })
})
