import { t } from '@/i18n'

export function imageSummary(
  format: string | null | undefined,
  metadata: Record<string, unknown>
): string {
  const parts = [format?.toUpperCase()]
  const bits = Number(metadata.bitpix ?? metadata.pixel_type)
  if ([-32, -64].includes(bits))
    parts.push(t('astrophotoflow.nodeUi.floatBits', { bits: -bits }))
  else if ([8, 16, 32, 64].includes(bits))
    parts.push(t('astrophotoflow.nodeUi.integerBits', { bits }))
  const shape = Array.isArray(metadata.shape) ? metadata.shape : []
  const planar =
    shape.length === 2 ||
    (shape.length === 3 && metadata.colour_layout === 'planar')
  const width = metadata.width ?? (planar ? shape.at(-1) : undefined)
  const height = metadata.height ?? (planar ? shape.at(-2) : undefined)
  if (typeof width === 'number' && typeof height === 'number') {
    parts.push(`${width} × ${height}`)
  }
  return parts.filter(Boolean).join(' · ')
}
