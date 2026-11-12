<script setup lang="ts">
import { computed, ref, watch } from 'vue'

type Point = [number, number]
const { kind, points, image, width, height, labels } = defineProps<{
  kind: 'points' | 'region' | 'line' | 'curve'
  points: readonly Point[]
  image?: string
  width: number
  height: number
  labels: { edit: string; remove: string; clear: string; second: string }
}>()
const emit = defineEmits<{ edit: [points: Point[]]; inspect: [point: Point] }>()
const start = ref<Point>()
const selected = ref<number>()
watch(
  () => [image, kind],
  () => {
    start.value = undefined
    selected.value = undefined
  }
)

function display([x, y]: Point): Point {
  return [x, kind === 'curve' ? 1 - y : y]
}
const positions = computed(() => points.map(display))
const radius = computed(() => Math.min(width, height) / 55)
const endpoints = computed(() =>
  positions.value.length === 2 ? positions.value : undefined
)
const polyline = computed(() =>
  positions.value.map((point) => point.join(',')).join(' ')
)

function place(event: MouseEvent) {
  const svg = event.currentTarget
  if (!(svg instanceof SVGSVGElement)) return
  const matrix = svg.getScreenCTM()
  if (!matrix) return
  const { x, y } = new DOMPoint(event.clientX, event.clientY).matrixTransform(
    matrix.inverse()
  )
  if (x < 0 || x >= width || y < 0 || y >= height) return
  const point: Point =
    kind === 'curve'
      ? [Math.round(x * 1000) / 1000, Math.round((1 - y) * 1000) / 1000]
      : [Math.floor(x), Math.floor(y)]
  if (kind === 'points') {
    selected.value = points.length
    emit('edit', [...points, point])
  } else if (kind === 'curve') {
    const next = [
      ...points.filter(([existing]) => existing !== point[0]),
      point
    ].sort((a, b) => a[0] - b[0])
    selected.value = next.indexOf(point)
    emit('edit', next)
  } else if (!start.value) {
    start.value = point
  } else {
    if (
      kind === 'region' &&
      (start.value[0] === point[0] || start.value[1] === point[1])
    )
      return
    if (start.value[0] === point[0] && start.value[1] === point[1]) return
    selected.value = 1
    emit('edit', [start.value, point])
    start.value = undefined
  }
}

function remove() {
  const index = selected.value ?? points.length - 1
  selected.value = undefined
  emit(
    'edit',
    kind === 'region' || kind === 'line'
      ? []
      : points.filter((_, i) => i !== index)
  )
}

function select(index: number) {
  const point = points[index]
  if (!point) return
  selected.value = index
  emit('inspect', point)
}

function clear() {
  start.value = undefined
  selected.value = undefined
  emit('edit', [])
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <svg
      role="group"
      :aria-label="labels.edit"
      :viewBox="`0 0 ${width} ${height}`"
      class="h-48 w-full cursor-crosshair rounded bg-component-node-widget-background"
      data-testid="bundle-geometry"
      @click="place"
    >
      <image v-if="image" :href="image" :width="width" :height="height" />
      <rect
        v-if="kind === 'region' && endpoints"
        :x="Math.min(endpoints[0]![0], endpoints[1]![0])"
        :y="Math.min(endpoints[0]![1], endpoints[1]![1])"
        :width="Math.abs(endpoints[1]![0] - endpoints[0]![0])"
        :height="Math.abs(endpoints[1]![1] - endpoints[0]![1])"
        fill="none"
        stroke="#7eb8ff"
        vector-effect="non-scaling-stroke"
      />
      <polyline
        v-if="kind === 'curve' || kind === 'line'"
        :points="polyline"
        fill="none"
        stroke="#7eb8ff"
        vector-effect="non-scaling-stroke"
      />
      <circle
        v-for="([x, y], index) in positions"
        :key="index"
        :cx="x"
        :cy="y"
        :r="radius"
        tabindex="0"
        role="button"
        :aria-label="`${index + 1}: ${points[index]?.join(', ')}`"
        :fill="selected === index ? '#ffba6a' : '#7eb8ff'"
        stroke="#181b20"
        vector-effect="non-scaling-stroke"
        @click.stop="select(index)"
        @keydown.enter.stop="select(index)"
      />
      <circle
        v-if="start"
        :cx="start[0]"
        :cy="start[1]"
        :r="radius"
        fill="#ffba6a"
      />
    </svg>
    <div class="flex items-center gap-2 text-muted-foreground">
      <span v-if="start">{{ labels.second }}</span>
      <span v-else class="tabular-nums">{{ points.length }}</span>
      <button
        v-if="points.length"
        type="button"
        class="ml-auto underline"
        @click="remove"
      >
        {{ labels.remove }}
      </button>
      <button
        v-if="points.length || start"
        type="button"
        class="underline"
        @click="clear"
      >
        {{ labels.clear }}
      </button>
    </div>
  </div>
</template>
