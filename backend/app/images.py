import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from backend.app.errors import APIError

FORMATS = {"image/jpeg": ("JPEG", {".jpg", ".jpeg"}), "image/png": ("PNG", {".png"})}


def validate_image(data: bytes, filename: str, content_type: str, settings) -> tuple[int, int, str]:
    if content_type not in FORMATS:
        raise APIError(415, "unsupported_media_type", "Chỉ chấp nhận ảnh JPEG hoặc PNG.")
    expected_format, extensions = FORMATS[content_type]
    if Path(filename).suffix.lower() not in extensions:
        raise APIError(415, "unsupported_media_type", "Phần mở rộng không khớp loại ảnh.")
    if not data:
        raise APIError(422, "empty_file", "File ảnh rỗng.")
    if len(data) > settings.max_upload_bytes:
        raise APIError(413, "file_too_large", "Ảnh vượt quá kích thước cho phép.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != expected_format:
                    raise APIError(415, "unsupported_media_type", "Nội dung file không khớp loại ảnh.")
                width, height = image.size
                if width * height > settings.max_image_pixels:
                    raise APIError(413, "image_too_large", "Ảnh có quá nhiều pixel.")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise APIError(413, "image_too_large", "Ảnh có quá nhiều pixel.") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise APIError(422, "invalid_image", "Không thể giải mã ảnh hoặc ảnh bị hỏng.") from None
    return width, height, ".jpg" if expected_format == "JPEG" else ".png"
