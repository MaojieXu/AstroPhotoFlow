# Previews and caches

English | [中文](previews.md)

Thumbnails and large-image viewing share one set of derived caches; caches are rebuildable and never serve as scientific input. The implementation lives in the data module's media and previews code (`src/astrophotoflow/modules/data/media/`); module responsibilities are in [architecture](../architecture.en.md).

## Thumbnails

- The background generates a 100px-longest-edge JPEG for every image that can be previewed automatically, without blocking an import.
- A fixed dataset uses the recipe of its first member in fixed version order; independent assets are computed separately, and an unavailable reference frame is not replaced by another.
- The web page raises fetch priority for the viewport and nearby rows, with at most 4 requests per page, and each cell is replaced once its cache key becomes ready.
- Known failed or unsupported entries stop being fetched repeatedly, explicit retry uses the batch endpoint, and the backend sweeps lost files in batches and recovers after restarts.

## Large-image viewing

- Saved recipes are reused; when missing, only the explicit reference frame is computed, overviews sample at 512, 1024 or 2048px, and zoomed tiles read regions on demand.
- `consumer_id` and `generation` only cancel the current viewing request and never write caches, scientific records or workflows; switching discards stale responses.
- Video prefers native HTML video with Range streaming; incompatible codecs and SER generate an H.264 proxy with a longest edge of at most 1920px on demand.
- A missing FFmpeg, mismatched timestamps or an exceeded budget fails explicitly, and no tool is downloaded automatically.

## Cache budgets

- The browser keeps 128 tiles at 512px RGBA, at most 128MiB, and the backend keeps at most 256MiB of encoded tile bytes.
- Disk usage is at most 4GiB including display bases, tiles, proxies and frame maps, stored under the actual `data_dir/previews/{version}/media/{key}/`.
- Only previews-owned derived files are evicted; originals and scientific records are kept, and in-progress ownership blocks concurrent permanent cleanup.

## States and failures

- States are `not_ready`, `generating`, `available`, `failed` and `unsupported`; generating returns 202, otherwise the current state is returned.
- A failed cache keeps its error and can be retried by explicit scheduling; startup marks interrupted generating entries as retryable failures, and shutdown drains.
- X-Trans or Quad Bayer data without demosaicing is viewed as a native-size grayscale mosaic with an explicit notice.

## Display recipes

- Known-classification datasets use the established MTF and background white-balance recipe during import, while other sources keep percentile thumbnails.
- RGB first estimates background white balance and then applies the stretch, Mono only stretches; the recipe is stored as a preview record and a display cache is not registered as a scientific asset.
- A recipe is keyed by fixed version, HDU, size and algorithm version; a generation in progress for the same version is shared, and a request waiting for an older recipe adds the automatic recipe after it finishes.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/data/previews.py` and `media.py`.
- State and request models are in `src/astrophotoflow/contracts/previews.py`; fields follow the [OpenAPI snapshot](../api/openapi.json).
- Shared-scope and project-scope viewing addresses are maintained in `src/astrophotoflow/modules/data/media/links.py`; tests are `tests/modules/data/test_display_previews.py` and `test_auto_stretch.py`.
