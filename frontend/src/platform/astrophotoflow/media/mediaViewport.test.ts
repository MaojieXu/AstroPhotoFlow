import OpenSeadragon from 'openseadragon'
import { describe, expect, it } from 'vitest'

import {
  actualPixelZoom,
  imageScreenBounds,
  imageZoomPercent,
  tileAddress
} from './viewport'

describe('original-pixel viewport coordinates', () => {
  it.each([1, 1.25, 2])(
    'keeps 100 percent at one source pixel per device pixel for density %s',
    (density) => {
      const item = {
        imageToViewportZoom: (zoom: number) => zoom * 5,
        viewportToImageZoom: (zoom: number) => zoom / 5
      }
      const zoom = actualPixelZoom(item, density)
      expect(
        imageZoomPercent(item, { getZoom: () => zoom }, density)
      ).toBeCloseTo(100)
    }
  )

  it('requests the selected source level and region including zero coordinates', () => {
    expect(
      tileAddress('/fixed/version/key/tiles/{level}/{x}/{y}', 14, 0, 9)
    ).toBe('/fixed/version/key/tiles/14/0/9')
  })

  it.each([
    { zoom: 0.16, left: 230, top: 120 },
    { zoom: 1, left: -1700, top: -950 },
    { zoom: 2, left: -3200, top: -2100 }
  ])(
    'aligns the overview to the current tile rectangle at $zoom zoom',
    ({ zoom, left, top }) => {
      const item = {
        getBounds: (current?: boolean) => {
          expect(current).toBe(true)
          return new OpenSeadragon.Rect(0, 0, 1, 2822 / 4144)
        }
      }
      const viewport = {
        pixelFromPoint: (point: OpenSeadragon.Point, current?: boolean) => {
          expect(current).toBe(true)
          return new OpenSeadragon.Point(
            left + point.x * 4144 * zoom,
            top + point.y * 4144 * zoom
          )
        }
      }
      const bounds = imageScreenBounds(item, viewport)
      expect(bounds.left).toBe(left)
      expect(bounds.top).toBe(top)
      expect(bounds.width).toBeCloseTo(4144 * zoom)
      expect(bounds.height).toBeCloseTo(2822 * zoom)
    }
  )
})
