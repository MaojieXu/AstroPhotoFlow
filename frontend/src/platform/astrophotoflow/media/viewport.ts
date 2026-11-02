import OpenSeadragon from 'openseadragon'
import type { MediaState } from '@astrophotoflow/ui'

export const BROWSER_TILE_LIMIT = 128

export function actualPixelZoom(
  item: Pick<OpenSeadragon.TiledImage, 'imageToViewportZoom'>,
  density: number
) {
  return item.imageToViewportZoom(1 / density)
}

export function imageZoomPercent(
  item: Pick<OpenSeadragon.TiledImage, 'viewportToImageZoom'>,
  viewport: Pick<OpenSeadragon.Viewport, 'getZoom'>,
  density: number
) {
  return item.viewportToImageZoom(viewport.getZoom()) * density * 100
}

export type ImageViewportSnapshot = {
  width: number
  height: number
  center: [number, number]
  zoom: number
}
export type ImageScreenBounds = {
  left: number
  top: number
  width: number
  height: number
}

export function imageScreenBounds(
  item: Pick<OpenSeadragon.TiledImage, 'getBounds'>,
  viewport: Pick<OpenSeadragon.Viewport, 'pixelFromPoint'>
): ImageScreenBounds {
  const bounds = item.getBounds(true)
  const start = viewport.pixelFromPoint(bounds.getTopLeft(), true)
  const end = viewport.pixelFromPoint(bounds.getBottomRight(), true)
  return {
    left: start.x,
    top: start.y,
    width: end.x - start.x,
    height: end.y - start.y
  }
}

export function createImageViewport(
  element: HTMLElement,
  image: MediaState,
  options: {
    previous?: ImageViewportSnapshot
    zoom: (percent: number) => void
    bounds: (bounds: ImageScreenBounds) => void
    failed: () => void
  }
) {
  const source = new OpenSeadragon.TileSource({
    width: image.width,
    height: image.height,
    tileSize: image.tile_size,
    tileOverlap: 0,
    minLevel: 0,
    maxLevel: image.max_level
  })
  source.getTileUrl = (level, x, y) => tileAddress(image.tile_url!, level, x, y)
  const viewer = OpenSeadragon({
    element,
    tileSources: [source],
    showNavigationControl: false,
    showNavigator: true,
    navigatorPosition: 'BOTTOM_RIGHT',
    navigatorAutoFade: false,
    navigatorSizeRatio: 0.17,
    drawer: 'canvas',
    maxImageCacheCount: BROWSER_TILE_LIMIT,
    imageLoaderLimit: 4,
    loadTilesWithAjax: true,
    tileRetryMax: 0,
    animationTime: 0.12,
    blendTime: 0,
    maxZoomPixelRatio: 16,
    minZoomImageRatio: Math.min(
      0.2,
      0.5 /
        ((window.devicePixelRatio || 1) *
          Math.min(
            element.clientWidth / image.width,
            element.clientHeight / image.height
          ))
    ),
    visibilityRatio: 0.75,
    gestureSettingsMouse: {
      clickToZoom: false,
      dblClickToZoom: false,
      scrollToZoom: true,
      dragToPan: true
    }
  })
  function actual() {
    const item = viewer.world.getItemAt(0)
    if (item)
      viewer.viewport.zoomTo(
        actualPixelZoom(item, window.devicePixelRatio || 1)
      )
  }
  function updateBounds() {
    const item = viewer.world.getItemAt(0)
    if (item) options.bounds(imageScreenBounds(item, viewer.viewport))
  }
  viewer.addHandler('open', () => {
    const item = viewer.world.getItemAt(0)
    if (
      item &&
      options.previous?.width === image.width &&
      options.previous.height === image.height
    ) {
      viewer.viewport.zoomTo(
        item.imageToViewportZoom(options.previous.zoom),
        undefined,
        true
      )
      viewer.viewport.panTo(
        new OpenSeadragon.Point(...options.previous.center),
        true
      )
    }
    updateBounds()
  })
  viewer.addHandler('after-resize', updateBounds)
  viewer.addHandler('viewport-change', () => {
    const item = viewer.world.getItemAt(0)
    if (!item) return
    updateBounds()
    const percent = imageZoomPercent(
      item,
      viewer.viewport,
      window.devicePixelRatio || 1
    )
    options.zoom(percent)
    viewer.drawer.setImageSmoothingEnabled(percent < 100)
    viewer.navigator?.element.style.setProperty(
      'visibility',
      viewer.viewport.getZoom() > viewer.viewport.getHomeZoom() * 1.01
        ? 'visible'
        : 'hidden'
    )
  })
  viewer.addHandler('canvas-double-click', (event) => {
    event.preventDefaultAction = true
    const item = viewer.world.getItemAt(0)
    if (!item) return
    const percent = imageZoomPercent(
      item,
      viewer.viewport,
      window.devicePixelRatio || 1
    )
    if (Math.abs(percent - 100) < 1) viewer.viewport.goHome()
    else
      viewer.viewport.zoomTo(
        actualPixelZoom(item, window.devicePixelRatio || 1),
        viewer.viewport.pointFromPixel(event.position)
      )
  })
  viewer.addHandler('tile-load-failed', options.failed)
  return {
    actual,
    fit: () => {
      viewer.viewport.goHome()
    },
    zoomBy: (factor: number) => {
      viewer.viewport.zoomBy(factor)
    },
    destroy: () => {
      viewer.destroy()
    },
    snapshot: (): ImageViewportSnapshot | undefined => {
      const item = viewer.world.getItemAt(0)
      if (!item) return
      const center = viewer.viewport.getCenter()
      return {
        width: image.width,
        height: image.height,
        center: [center.x, center.y],
        zoom: item.viewportToImageZoom(viewer.viewport.getZoom())
      }
    }
  }
}

export function tileAddress(
  template: string,
  level: number,
  x: number,
  y: number
) {
  return template
    .replace('{level}', String(level))
    .replace('{x}', String(x))
    .replace('{y}', String(y))
}
