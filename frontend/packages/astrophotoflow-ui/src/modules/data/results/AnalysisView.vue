<script setup lang="ts">
import { computed, ref } from 'vue'

import type {
  AnalysisResult,
  MediaPosition
} from '../../../generated/api/types.gen'

const { result, labels, baseline, selectable, position } = defineProps<{
  result: AnalysisResult
  baseline?: AnalysisResult
  selectable?: boolean
  position?: MediaPosition
  labels: {
    unavailable: string
    logarithmic: string
    source: string
    unit: string
    chart: string
    before?: string
    current?: string
    frame?: string
  }
}>()
const emit = defineEmits<{ select: [position: MediaPosition] }>()
const logarithmic = ref(false)

function series(value: AnalysisResult) {
  const histogram = value.histogram
  if (histogram) {
    return histogram.counts.map(
      (count, index) =>
        [
          histogram.edges[index]! / 2 + histogram.edges[index + 1]! / 2,
          count
        ] as const
    )
  }
  return value.rows.flatMap((row) =>
    typeof row[0] === 'number' &&
    typeof row[1] === 'number' &&
    Number.isFinite(row[0]) &&
    Number.isFinite(row[1])
      ? [[row[0], row[1]] as const]
      : []
  )
}

const points = computed(() => series(result))
const previous = computed(() => (baseline ? series(baseline) : []))
const canLog = computed(() =>
  [...points.value, ...previous.value].every((point) => point[1] >= 0)
)
const stroke = computed(() => {
  switch (result.histogram?.channel) {
    case 'red':
      return '#ef747c'
    case 'green':
      return '#65ca9b'
    case 'blue':
      return '#6eaeff'
    case 'composite':
      return '#8ebaff'
    default:
      return 'currentColor'
  }
})
const range = computed(() => {
  const data = [...points.value, ...previous.value]
  if (!data.length) return { path: '', baseline: '', x: [0, 0], y: [0, 0] }
  const yValue = (value: number) =>
    logarithmic.value && canLog.value ? Math.log1p(value) : value
  let xMin = Infinity,
    xMax = -Infinity,
    yMin = Infinity,
    yMax = -Infinity
  for (const [x, y] of data) {
    xMin = Math.min(xMin, x)
    xMax = Math.max(xMax, x)
    yMin = Math.min(yMin, y)
    yMax = Math.max(yMax, y)
  }
  const x0 = result.histogram?.edges[0] ?? xMin
  const x1 = result.histogram?.edges.at(-1) ?? xMax
  const y0 = yValue(Math.min(0, yMin))
  const y1 = yValue(yMax)
  const path = (values: ReturnType<typeof series>) =>
    values
      .map(
        ([x, y]) =>
          `${((x - x0) / (x1 - x0 || 1)) * 500 + 6},${190 - ((yValue(y) - y0) / (y1 - y0 || 1)) * 180}`
      )
      .join(' ')
  return {
    path: path(points.value),
    baseline: path(previous.value),
    x: [x0, x1],
    y: [yMin, yMax]
  }
})

function display(value: unknown) {
  return value === null || value === undefined
    ? labels.unavailable
    : typeof value === 'object'
      ? JSON.stringify(value)
      : String(value)
}
</script>

<template>
  <section class="min-w-0 space-y-2 text-xs">
    <p class="m-0 font-medium">{{ result.title }}</p>
    <p class="m-0 break-words text-muted-foreground">
      {{ labels.source }}: {{ result.source
      }}<template
        v-if="
          result.unit ||
          ['metrics', 'table', 'series', 'histogram'].includes(result.kind)
        "
      >
        · {{ labels.unit }}: {{ result.unit ?? labels.unavailable }}</template
      >
    </p>
    <template v-if="result.kind === 'series' || result.kind === 'histogram'">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <label v-if="canLog" class="flex min-h-8 items-center gap-2">
          <input v-model="logarithmic" type="checkbox" />{{
            labels.logarithmic
          }}
        </label>
        <div v-if="baseline" class="ml-auto flex gap-3 text-muted-foreground">
          <span class="inline-flex items-center gap-1"
            ><i class="w-3 border-t border-dashed" />{{ labels.before }}</span
          >
          <span class="inline-flex items-center gap-1"
            ><i class="w-3 border-t" :style="{ borderColor: stroke }" />{{
              labels.current
            }}</span
          >
        </div>
      </div>
      <svg
        viewBox="0 0 512 200"
        role="img"
        :aria-label="labels.chart"
        class="w-full rounded-sm border border-border-default bg-component-node-widget-background text-foreground"
      >
        <polyline
          v-if="range.baseline"
          :points="range.baseline"
          data-testid="bundle-histogram-baseline"
          fill="none"
          stroke="#9ca3af"
          stroke-opacity="0.65"
          stroke-dasharray="5 4"
          stroke-width="1.5"
          vector-effect="non-scaling-stroke"
        />
        <polyline
          :points="range.path"
          fill="none"
          :stroke="stroke"
          stroke-width="1.5"
          vector-effect="non-scaling-stroke"
        />
      </svg>
      <div class="flex justify-between tabular-nums">
        <span
          >{{ result.histogram?.intensity_unit ?? result.columns[0] }}:
          {{ range.x.join(' – ') }}</span
        >
        <span
          >{{ result.histogram ? result.unit : result.columns[1] }}:
          {{ range.y.join(' – ') }}</span
        >
      </div>
    </template>
    <div v-else-if="result.kind === 'table'" class="max-h-64 overflow-auto">
      <table class="w-full border-collapse text-left tabular-nums">
        <thead>
          <tr>
            <th v-if="selectable && result.row_positions" class="p-1">
              {{ labels.frame }}
            </th>
            <th
              v-for="(column, index) in result.columns"
              :key="index"
              class="sticky top-0 bg-component-node-widget-background p-1"
            >
              {{ column }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rowIndex) in result.rows" :key="rowIndex">
            <td
              v-if="selectable && result.row_positions"
              class="border-t border-border-default p-1"
            >
              <button
                v-if="result.row_positions[rowIndex]"
                type="button"
                class="rounded px-1 underline focus-visible:outline"
                :aria-current="
                  position?.member_index ===
                    result.row_positions[rowIndex]?.member_index &&
                  (position?.frame_index ?? 0) ===
                    (result.row_positions[rowIndex]?.frame_index ?? 0)
                    ? 'true'
                    : undefined
                "
                @click="emit('select', result.row_positions[rowIndex]!)"
              >
                {{
                  (result.row_positions[rowIndex]!.frame_index ??
                    result.row_positions[rowIndex]!.member_index) + 1
                }}
              </button>
            </td>
            <td
              v-for="(value, columnIndex) in row"
              :key="columnIndex"
              class="border-t border-border-default p-1"
            >
              {{ display(value) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <dl
      v-else-if="result.kind === 'metrics'"
      class="m-0 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-3 gap-y-1"
    >
      <template v-for="(value, key) in result.values" :key="key">
        <dt class="break-words text-muted-foreground">{{ key }}</dt>
        <dd class="m-0 break-words tabular-nums">{{ display(value) }}</dd>
      </template>
    </dl>
    <pre
      v-else
      class="m-0 max-h-64 overflow-auto whitespace-pre-wrap break-words"
      >{{
        result.kind === 'json'
          ? JSON.stringify(result.values, null, 2)
          : result.text
      }}</pre>
    <p v-if="result.sample" class="m-0 break-words text-muted-foreground">
      {{ result.sample }}
    </p>
  </section>
</template>
