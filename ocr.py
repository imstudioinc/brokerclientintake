"""Text out of a PDF: the text layer when there is one, otherwise Windows' built-in OCR.

Windows OCR (Windows.Media.Ocr) ships with Windows 10/11, so nothing is installed on the
work computer; the Python side needs the winrt packages (bundled in the exe).
"""
import asyncio
import io

import pdfplumber
import pypdfium2 as pdfium


class OcrUnavailable(Exception):
    pass


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


def is_image(path):
    return str(path).lower().endswith(tuple(IMAGE_EXTS))


def text_lines(pdf_path):
    """Lines of the PDF's text layer, or [] for a scanned / image-only PDF (or a photo)."""
    if is_image(pdf_path):
        return []
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    return [l for l in text.splitlines() if l.strip()]


async def _recognize(png_bytes):
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png_bytes)
    await writer.store_async()
    stream.seek(0)
    bitmap = await (await BitmapDecoder.create_async(stream)).get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise OcrUnavailable("Windows has no OCR language installed")
    result = await engine.recognize_async(bitmap)
    return [(w.bounding_rect.x, w.bounding_rect.y, w.bounding_rect.width, w.bounding_rect.height, w.text)
            for line in result.lines for w in line.words]


def page_images(pdf_path, scale=4):
    """Each page as a black-on-white image (light coloured backgrounds, e.g. highlights, removed).

    A photo or screenshot comes back three times, prepared differently (smooth, black-and-white,
    bigger): small screen text reads differently each way, so the caller combines what each finds."""
    if is_image(pdf_path):
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(pdf_path)).convert("L")
        k = max(1, 3 if img.width < 1600 else 2 if img.width < 2400 else 1)
        big = img.resize((img.width * k, img.height * k), Image.LANCZOS)
        yield big
        yield big.point(lambda v: 0 if v < 200 else 255)
        k2 = 2400 / img.width if img.width < 2400 else 1
        yield img.resize((int(img.width * k2), int(img.height * k2))).point(lambda v: 0 if v < 200 else 255)
        return
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for page in doc:
            img = page.render(scale=scale).to_pil().convert("L")
            yield img.point(lambda v: 0 if v < 200 else 255)
    finally:
        doc.close()


def words(img):
    """[(x, y, w, h, text)] for one image."""
    try:
        import winrt.windows.media.ocr  # noqa: F401
    except ImportError as e:
        raise OcrUnavailable("Windows OCR is not available in this build") from e
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return asyncio.run(_recognize(buf.getvalue()))


def rows(word_list):
    """Group words into text rows by their vertical position (OCR returns label and value apart)."""
    out = []
    for x, y, w, h, t in sorted(word_list, key=lambda v: (v[1], v[0])):
        if out and abs(out[-1][0] - y) < h * 0.6:
            out[-1][1].append((x, t))
        else:
            out.append([y, [(x, t)]])
    return [" ".join(t for _, t in sorted(ws)) for _, ws in out]
