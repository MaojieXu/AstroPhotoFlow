from __future__ import annotations
from io import BytesIO
from pathlib import Path
import rawpy
from PIL import Image, ImageOps

def read_raw_preview(path: Path, max_edge: int=100) -> Image.Image:
    with rawpy.imread(str(path)) as raw:
        source_edge = max(raw.sizes.width, raw.sizes.height)
        threshold = min(max_edge, source_edge)
        try:
            thumbnail = raw.extract_thumb()
            if thumbnail.format == rawpy.ThumbFormat.JPEG:
                with Image.open(BytesIO(thumbnail.data)) as image:
                    if max(image.size) >= threshold:
                        return ImageOps.exif_transpose(image).convert('RGB').copy()
            elif thumbnail.format == rawpy.ThumbFormat.BITMAP:
                image = Image.fromarray(thumbnail.data)
                if max(image.size) >= threshold:
                    return image.convert('RGB').copy()
        except (rawpy.LibRawError, OSError, ValueError):
            pass
        return Image.fromarray(raw.postprocess(half_size=source_edge // 2 >= max_edge, output_bps=8, output_color=rawpy.ColorSpace.sRGB)).convert('RGB')
