import { useResizeObserver } from '@vueuse/core'
import { ref, toValue, watch } from 'vue'
import type { MaybeRefOrGetter, Ref } from 'vue'

import type { ComponentWidget } from '@/scripts/domWidget'

/** Measure intrinsic content, independently of the node's previous allocated height. */
export function useNodeWidgetSize(
  source: MaybeRefOrGetter<ComponentWidget<string | object>>,
  content: Ref<HTMLElement | undefined>
) {
  const height = ref(0)
  let owner: ComponentWidget<string | object> | undefined
  function resize(measured: number) {
    const widget = toValue(source)
    if (
      !widget.node.graph ||
      measured <= 0 ||
      (measured === height.value && widget === owner)
    )
      return
    const newOwner = owner !== widget
    owner = widget
    height.value = measured
    widget.options.getMinHeight = () => height.value
    widget.options.getMaxHeight = () => height.value
    const node = widget.node
    if (newOwner) {
      // Native DOM measurements supply the rendered extent. Keep view-only
      // expansion out of the serialized geometry and canvas content marker.
      const minimum = Math.max(0, node.computeSize()[1] - measured)
      node.setSize([node.size[0], minimum])
    }
    node.setDirtyCanvas(true, true)
  }
  useResizeObserver(content, ([entry]) => {
    if (entry)
      resize(
        Math.ceil(
          entry.borderBoxSize?.[0]?.blockSize ?? entry.contentRect.height
        )
      )
  })
  watch(
    () => toValue(source),
    () => {
      if (content.value) resize(content.value.offsetHeight)
    },
    { flush: 'post' }
  )
}
