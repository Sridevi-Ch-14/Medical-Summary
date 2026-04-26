"""
ClinIQ - PDF Extractor (Phase 1)
==================================
Hybrid extraction: pdfplumber for digital PDFs,
pytesseract fallback for scanned/image-embedded PDFs.
"""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using a hybrid strategy.
    
    1. Try pdfplumber (fast, works for digital/text PDFs)
    2. If text is sparse (<50 chars per page avg), fall back to OCR via pytesseract
    3. Clean the extracted text with regex
    4. Pre-clean: remove interpretation blocks before parser sees them
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Cleaned extracted text
    """
    file_path = str(Path(file_path).resolve())
    logger.info(f"Extracting text from PDF: {file_path}")

    # Try digital extraction first
    text = _extract_digital(file_path)

    # If digital extraction yields very little text, try OCR
    if _is_sparse_text(text, file_path):
        logger.info("Digital extraction sparse — falling back to OCR...")
        ocr_text = _extract_ocr(file_path)
        if len(ocr_text.strip()) > len(text.strip()):
            text = ocr_text

    cleaned = _clean_text(text)
    
    # Pre-clean: Remove interpretation blocks & lab method noise
    # This prevents 'Excellent Control' and 'Photometric' from reaching the parser
    final = _pre_clean_medical(cleaned)
    
    logger.info(f"Extracted {len(final)} characters from PDF")
    return final


def _extract_digital(file_path: str) -> str:
    """Extract text using pdfplumber (handles digital PDFs with text layers)."""
    try:
        import pdfplumber

        full_text = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract regular text
                page_text = page.extract_text() or ""

                # Also try to extract tables and convert to text
                tables = page.extract_tables() or []
                table_text = ""
                for table in tables:
                    for row in table:
                        if row:
                            # Filter None values and join cells
                            cells = [str(cell).strip() if cell else "" for cell in row]
                            table_text += "    ".join(cells) + "\n"

                # Combine: use table text if it gives more structured data
                combined = page_text
                if table_text and len(table_text.strip()) > 20:
                    combined = page_text + "\n" + table_text

                if combined.strip():
                    full_text.append(f"--- Page {page_num} ---\n{combined}")

        return "\n\n".join(full_text)

    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return ""
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return ""


def _extract_ocr(file_path: str) -> str:
    """
    Extract text using Tesseract OCR (for scanned PDFs / image-embedded PDFs).
    Converts each PDF page to an image, then runs OCR.
    """
    try:
        import pytesseract
        from PIL import Image
        import os

        # Try to set tesseract path on Windows
        tesseract_path = os.environ.get(
            "TESSERACT_PATH",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

    except ImportError:
        logger.warning("pytesseract not installed. OCR fallback unavailable.")
        return ""

    try:
        # Use pdf2image to convert PDF pages to images
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(file_path, dpi=300)
        except ImportError:
            # Alternative: use pdfplumber to get page images
            logger.warning("pdf2image not available. Trying pdfplumber for page images...")
            try:
                import pdfplumber
                images = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        img = page.to_image(resolution=300)
                        images.append(img.original)
            except Exception as e:
                logger.error(f"Cannot convert PDF pages to images: {e}")
                return ""

        full_text = []
        for i, img in enumerate(images, 1):
            page_text = pytesseract.image_to_string(img, lang="eng")
            if page_text.strip():
                full_text.append(f"--- Page {i} ---\n{page_text}")

        return "\n\n".join(full_text)

    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return ""


def _is_sparse_text(text: str, file_path: str) -> bool:
    """
    Determine if extracted text is too sparse (likely a scanned PDF).
    Returns True if average characters per page is below threshold.
    """
    if not text.strip():
        return True

    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            num_pages = len(pdf.pages)
    except Exception:
        num_pages = 1

    chars_per_page = len(text.strip()) / max(num_pages, 1)
    return chars_per_page < 50  # Less than 50 chars/page = probably scanned


def _clean_text(raw_text: str) -> str:
    """
    Clean extracted text by removing noise common in medical reports.
    
    Removes:
    - Page markers (--- Page N ---)
    - Excessive whitespace
    - Common headers/footers (Page X of Y, confidential notices)
    - Non-printable characters
    - Repeated separator lines
    """
    text = raw_text

    # Remove page markers (our own markers from extraction)
    text = re.sub(r'---\s*Page\s*\d+\s*---', '', text)

    # Remove common headers/footers
    text = re.sub(r'Page\s+\d+\s+of\s+\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'CONFIDENTIAL.*?(?:\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'printed\s+on.*?(?:\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'end\s+of\s+report', '', text, flags=re.IGNORECASE)

    # Remove repeated separator lines (===, ---, ***)
    text = re.sub(r'[=\-*_]{5,}', '', text)

    # Remove non-printable characters (keep newlines, tabs, spaces)
    text = re.sub(r'[^\x20-\x7E\n\t]', '', text)

    # Collapse multiple blank lines into one
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Collapse multiple spaces into one
    text = re.sub(r' {2,}', '  ', text)

    return text.strip()


def _pre_clean_medical(text: str) -> str:
    """
    Medical-specific pre-cleaning at the extraction level.
    Removes interpretation blocks, control labels, and junk that would
    confuse the downstream parser if left intact.
    
    This runs BEFORE the parser's own noise filter for defense in depth.
    """
    # Remove entire INTERPRETATION blocks (header + following lines until next section/blank)
    lines = text.split('\n')
    result = []
    skip = False
    
    # Junk line markers specific to Indian labs (Medicover, SRL, Thyrocare)
    junk_markers = [
        "INTERPRETATION", "Excellent Control", "Good Control", "Fair Control",
        "Poor Control", "Near Optimal", "Derived from", "Normal : <",
        "Normal : >", "Diabetic :", "Pre-Diabetic :", "Target :",
    ]
    
    for line in lines:
        stripped = line.strip()
        
        # Start of interpretation block
        if stripped.upper() == "INTERPRETATION":
            skip = True
            continue
        
        # End block on empty line or new section-like header
        if skip:
            if not stripped:
                skip = False
                result.append(line)
            elif stripped.isupper() and not any(c.isdigit() for c in stripped) and len(stripped.split()) <= 4:
                skip = False
                result.append(line)
            continue
        
        # Remove individual junk lines
        if any(marker.lower() in stripped.lower() for marker in junk_markers):
            continue
        
        result.append(line)
    
    return '\n'.join(result)
