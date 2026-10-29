const labels: Record<string, string> = {
  subframe: '单帧', masterframe: '合成帧', video: '视频',
  light: '亮场', bias: '偏置场', dark: '暗场', flat: '平场', dark_flat: '暗平场',
  intermediate: '中间结果', final: '最终结果', unknown: '未知', changed: '内容已变化', raw: '原始素材', calibration: '校准素材', result: '结果素材',
  standard: '常规', iso: 'ISO', gain: 'Gain／Offset',
  managed: '托管副本', reference: '仅引用', active: '启用', archived: '已归档',
  available: '原件可读', missing: '原件不可访问', unavailable: '不可用',
  mono: '单色', color: '彩色', mixed: '混合', partial: '部分缺失',
  file: '文件', manual: '人工填写', preset: '拍摄预设'
}

export function displayLabel(value: unknown) {
  return value == null || value === '' ? '未指定' : labels[String(value)] ?? String(value)
}

export function parameterSummary(value: { parameter_mode?: unknown; iso?: unknown; gain?: unknown; offset?: unknown }) {
  const number = (input: unknown) => input == null || input === '' ? '未指定' : displayLabel(input)
  if (value.parameter_mode === 'mixed') return '混合'
  if (value.parameter_mode === 'iso') return 'ISO · ' + number(value.iso)
  if (value.parameter_mode === 'gain') return 'Gain · ' + number(value.gain) + ' / Offset · ' + number(value.offset)
  const recorded = (['iso', 'gain', 'offset'] as const)
    .filter(key => value[key] != null && value[key] !== '')
    .map(key => `${key === 'iso' ? 'ISO' : key === 'gain' ? 'Gain' : 'Offset'} ${number(value[key])}`)
  return recorded.length ? '模式未指定 · ' + recorded.join(' / ') : '未指定'
}
