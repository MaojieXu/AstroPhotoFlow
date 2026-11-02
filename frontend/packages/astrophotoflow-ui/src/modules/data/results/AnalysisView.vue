<script setup lang="ts">
import { computed, ref } from 'vue'

import type { AnalysisResult } from '../../../generated/api/types.gen'

const { result, labels } = defineProps<{
  result: AnalysisResult
  labels: {
    unavailable: string
    logarithmic: string
    source: string
    unit: string
    chart: string
  }
}>()
const logarithmic = ref(false)
const points = computed(() =>
  result.rows.flatMap((row) =>
    typeof row[0] === 'number' &&
    typeof row[1] === 'number' &&
    Number.isFinite(row[0]) &&
    Number.isFinite(row[1])
      ? [[row[0], row[1]] as const]
      : []
  )
)
const canLog = computed(() => points.value.every((point) => point[1] >= 0))
const range = computed(() => {
  const data = points.value
  if (!data.length) return { path: '', x: [0, 0], y: [0, 0] }
  const xs = data.map((point) => point[0])
  const ys = data.map((point) =>
    logarithmic.value && canLog.value ? Math.log1p(point[1]) : point[1]
  )
  const x0 = Math.min(...xs),
    x1 = Math.max(...xs)
  const y0 = Math.min(0, ...ys),
    y1 = Math.max(...ys)
  return {
    path: data
      .map(
        (point, index) =>
          `${((point[0] - x0) / (x1 - x0 || 1)) * 500 + 6},${190 - (((ys[index] ?? 0) - y0) / (y1 - y0 || 1)) * 180}`
      )
      .join(' '),
    x: [x0, x1],
    y: [
      Math.min(...data.map((point) => point[1])),
      Math.max(...data.map((point) => point[1]))
    ]
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
          result.unit || ['metrics', 'table', 'series'].includes(result.kind)
        "
      >
        · {{ labels.unit }}: {{ result.unit ?? labels.unavailable }}</template
      >
    </p>
    <template v-if="result.kind === 'series'">
      <label v-if="canLog" class="flex min-h-8 items-center gap-2"
        ><input v-model="logarithmic" type="checkbox" />{{
          labels.logarithmic
        }}</label
      >
      <svg
        viewBox="0 0 512 200"
        role="img"
        :aria-label="labels.chart"
        class="w-full rounded-sm border border-border-default bg-component-node-widget-background text-foreground"
      >
        <polyline
          :points="range.path"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        />
      </svg>
      <div class="flex justify-between tabular-nums">
        <span>{{ result.columns[0] }}: {{ range.x.join(' – ') }}</span
        ><span>{{ result.columns[1] }}: {{ range.y.join(' – ') }}</span>
      </div>
    </template>
    <div v-else-if="result.kind === 'table'" class="max-h-64 overflow-auto">
      <table class="w-full border-collapse text-left tabular-nums">
        <thead>
          <tr>
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
      <template v-for="(value, key) in result.values" :key="key"
        ><dt class="break-words text-muted-foreground">{{ key }}</dt>
        <dd class="m-0 break-words tabular-nums">
          {{ display(value) }}
        </dd></template
      >
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
