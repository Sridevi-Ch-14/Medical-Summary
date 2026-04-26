"""
ClinIQ - Extraction Router (Phase 1)
======================================
Unified entry point that auto-detects file type
and routes to the correct extractor.

Supported formats:
  - .pdf  (digital + scanned/image-embedded)
  - .docx (Word documents)
  - .txt  (plain text)
"""

import logging
from pathlib import Path

from extractor.pdf_extractor import extract_text_from_pdf
from extractor.docx_extractor import extract_text_from_docx
from extractor.txt_extractor import extract_text_from_txt

logger = logging.getLogger(__name__)

# Supported file extensions and their extractors
SUPPORTED_EXTENSIONS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".txt": extract_text_from_txt,
}


def extract_text(file_path: str) -> str:
    """
    Universal text extraction entry point.
    
    Auto-detects the file type by extension and routes to
    the appropriate extractor. All extractors return cleaned,
    normalized text ready for the parsing pipeline.
    
    Args:
        file_path: Path to any supported document file
        
    Returns:
        Extracted and cleaned text
        
    Raises:
        ValueError: If file type is not supported
        FileNotFoundError: If file does not exist
    """
    path = Path(file_path)

    # Validate file exists
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Get file extension (lowercase)
    ext = path.suffix.lower()

    # Route to correct extractor
    if ext in SUPPORTED_EXTENSIONS:
        logger.info(f"Routing {path.name} ({ext}) to extractor...")
        extractor_fn = SUPPORTED_EXTENSIONS[ext]
        return extractor_fn(str(path))
    else:
        supported = ", ".join(SUPPORTED_EXTENSIONS.keys())
        raise ValueError(
            f"Unsupported file type: '{ext}'. Supported types: {supported}"
        )


def get_file_type(file_path: str) -> str:
    """Return the lowercase file extension of a given path."""
    return Path(file_path).suffix.lower()


def is_supported(file_path: str) -> bool:
    """Check if a file type is supported by the extraction engine."""
    return get_file_type(file_path) in SUPPORTED_EXTENSIONS
