import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AnalysisView from '@ui/modules/workflows/AnalysisView.vue'
import type { AnalysisResult } from '@ui/modules/workflows/results'

const labels = {
  unavailable: 'Unavailable',
  logarithmic: 'Log display',
  source: 'Source',
  unit: 'Unit',
  chart: 'Chart'
}
const metric: AnalysisResult = {
  kind: 'metrics',
  title: 'Background',
  source: 'Measured',
  unit: null,
  columns: [],
  rows: [],
  values: { known_zero: 0, missing: null },
  text: null,
  sample: 'Full selected member',
  member_index: 0
}

describe('shared analysis results', () => {
  it('keeps zero measurements distinct from unavailable values and units', () => {
    const wrapper = mount(AnalysisView, { props: { result: metric, labels } })
    expect(wrapper.findAll('dd').map((item) => item.text())).toEqual([
      '0',
      'Unavailable'
    ])
    expect(wrapper.text()).toContain('Unit: Unavailable')
  })

  it('renders a series including actual zero counts without exposing a logarithmic control for negative data', () => {
    const wrapper = mount(AnalysisView, {
      props: {
        labels,
        result: {
          ...metric,
          kind: 'series',
          columns: ['intensity', 'count'],
          rows: [
            [0, 0],
            [1, -2],
            [2, 3]
          ]
        }
      }
    })
    expect(wrapper.find('svg').attributes('aria-label')).toBe('Chart')
    expect(wrapper.find('polyline').attributes('points')).not.toBe('')
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
  })

  it('shows report text as text rather than executable markup', () => {
    const wrapper = mount(AnalysisView, {
      props: {
        labels,
        result: {
          ...metric,
          kind: 'text',
          text: '<script>unexpected()</script>'
        }
      }
    })
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('pre').text()).toContain(
      '<script>unexpected()</script>'
    )
  })
})
