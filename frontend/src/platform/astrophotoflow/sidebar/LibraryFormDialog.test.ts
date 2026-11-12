import userEvent from '@testing-library/user-event'
import { render, screen, waitFor } from '@testing-library/vue'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { defineComponent, ref } from 'vue'

import LibraryFormDialog from './LibraryFormDialog.vue'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

describe('library native form dialog', () => {
  it('does not focus a closed dialog when its translated title changes', async () => {
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    onTestFinished(() => focus.mockRestore())
    const { rerender } = render(LibraryFormDialog, { props: { open: false, title: '设备' } })
    await rerender({ title: 'Equipment' })
    expect(focus).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps one dialog and focuses the new view when its content changes', async () => {
    const Harness = defineComponent({
      components: { LibraryFormDialog },
      setup: () => ({ device: ref(false) }),
      template: `<LibraryFormDialog open :title="device ? 'New camera' : 'New combination'">
        <input v-if="device" key="device" autofocus aria-label="Device name" />
        <input v-else key="combination" autofocus aria-label="Combination name" />
        <button @click="device = true">New camera</button>
      </LibraryFormDialog>`
    })
    const user = userEvent.setup()
    render(Harness)
    await waitFor(() => expect(screen.getByLabelText('Combination name')).toHaveFocus())
    const dialog = screen.getByRole('dialog')
    await user.click(screen.getByRole('button', { name: 'New camera' }))
    await waitFor(() => expect(screen.getByLabelText('Device name')).toHaveFocus())
    expect(screen.getAllByRole('dialog')).toHaveLength(1)
    expect(screen.getByRole('dialog')).toBe(dialog)
  })

  it('blocks closing while saving and requests close on Escape afterwards', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(LibraryFormDialog, {
      props: { open: true, title: 'Combination', busy: true, onClose },
      slots: { default: '<input autofocus aria-label="Name" />' }
    })
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveFocus())
    expect(screen.getByRole('button', { name: 'g.close' })).toBeDisabled()
    await user.keyboard('{Escape}')
    expect(onClose).not.toHaveBeenCalled()
    await rerender({ busy: false })
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })
})
