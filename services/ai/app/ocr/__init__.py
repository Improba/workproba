"""OCR des pièces jointes (Mistral OCR en V2)."""

from app.ocr.detection import is_scanned_pdf
from app.ocr.mistral import MistralOcrClient, OcrResult

__all__ = [
    "MistralOcrClient",
    "OcrResult",
    "is_scanned_pdf",
]
