# ADR-APF-PREVIEW-0001: On-demand astronomy media viewing

Date: 2026-10-29

## Status

Accepted

## Context

AstroPhotoFlow groups can contain thousands of large subframes. Enlarging a 100-pixel thumbnail cannot expose original detail, while loading every full image or generating complete pyramids for all members scales with the entire collection. The scientific input remains a fixed data reference; viewing must not edit the graph or transfer Agent control.

## Decision

Use OpenSeadragon inside the existing native Vue and Reka Dialog shell. The data module owns original-resolution region reads, display recipes, cancellable preparation and disposable caches. The UI package exposes typed viewer requests; the host injects native rendering through its existing controls boundary.

Generate only requested levels and regions. Load the current member and prefetch at most adjacent thumbnails. Formats requiring complete decoding reuse a disposable current-image backing file. Display transformations are shared across tiles; source bytes and scientific references remain authoritative. Video uses HTML video playback with range streaming and optional display proxies; paused-frame magnification resolves original frames through timestamps or the proxy's frame map.

## Alternatives

A whole-image download is simpler but makes browser memory scale with image dimensions. Complete precomputed pyramids improve repeated arbitrary navigation but impose work and disk use for regions never viewed. A custom zoom engine avoids a dependency while duplicating tile scheduling, coordinate conversion and navigation maintained by OpenSeadragon.

## Consequences

Cache budgets constrain retained display data rather than decoder peak RSS. Eviction can require regeneration. Unsupported data layouts, missing codecs and unavailable originals remain explicit errors. Performance and visual acceptance require user verification; compiling this candidate does not establish either.
