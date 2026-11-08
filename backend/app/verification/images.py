"""Evidence image checks (sign-up form 9.2, 10.1): real type, editing-software metadata, a perceptual
hash for reuse detection, the cleaned JPEG that is kept, and the reviewer's watermark (6.1).

Pillow does the work (no pyvips or ClamAV on this deployment): opening the file proves its real type,
and re-encoding to a fresh JPEG drops every metadata block, GPS included.
"""

import io
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

MAX_PIXELS = 40_000_000
KEEP_LONG_EDGE = 2000  # sign-up form 9.2: re-encoded at most 2,000 px
MIN_SHORT_EDGE = 600
EXIF_SOFTWARE = 0x0131
EDITORS = ("photoshop", "gimp", "snapseed", "picsart", "lightroom", "canva", "pixlr", "facetune", "illustrator", "affinity")


class ImageRejected(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Cleaned:
    jpeg: bytes
    width: int
    height: int
    phash: bytes
    flags: list[str] = field(default_factory=list)


def dhash(picture: Image.Image) -> bytes:
    """64-bit difference hash: survives re-compression and resizing, so a re-uploaded ID photo matches."""
    small = picture.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if pixels[row * 9 + col] > pixels[row * 9 + col + 1] else 0)
    return bits.to_bytes(8, "big")


def hamming(a: bytes, b: bytes) -> int:
    return bin(int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).count("1")


def clean(data: bytes) -> Cleaned:
    flags: list[str] = []
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ("JPEG", "PNG", "WEBP"):
                raise ImageRejected("TYPE")
            width, height = probe.size
            if width * height > MAX_PIXELS:
                raise ImageRejected("TOO_MANY_PIXELS")
            software = str(probe.getexif().get(EXIF_SOFTWARE, "") or "").lower()
            if any(editor in software for editor in EDITORS):
                flags.append("editing_software")
            if probe.format == "PNG":
                flags.append("screenshot_suspected")  # phone cameras write JPEG; a PNG is usually a screenshot
            probe.load()
            picture = ImageOps.exif_transpose(probe)
    except ImageRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ImageRejected("BROKEN") from error
    picture = picture.convert("RGB")
    if min(picture.size) < MIN_SHORT_EDGE:
        flags.append("low_resolution")
    picture.thumbnail((KEEP_LONG_EDGE, KEEP_LONG_EDGE))
    out = io.BytesIO()
    picture.save(out, format="JPEG", quality=88)  # no exif/icc arguments: nothing carried over
    return Cleaned(out.getvalue(), picture.width, picture.height, dhash(picture), flags)


def watermark(jpeg: bytes, text: str) -> bytes:
    """A faint, repeated reviewer mark, so a screenshot of the evidence shows who looked at it."""
    with Image.open(io.BytesIO(jpeg)) as source:
        base = source.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    step_x, step_y = max(220, base.width // 4), max(120, base.height // 6)
    for y in range(0, base.height, step_y):
        for x in range(-step_x, base.width, step_x):
            draw.text((x + (y // step_y % 2) * step_x // 2, y), text, fill=(255, 255, 255, 70))
            draw.text((x + (y // step_y % 2) * step_x // 2 + 1, y + 1), text, fill=(0, 0, 0, 50))
    marked = Image.alpha_composite(base, layer).convert("RGB")
    out = io.BytesIO()
    marked.save(out, format="JPEG", quality=85)
    return out.getvalue()
