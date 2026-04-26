"""
ClinIQ - Plain Text Extractor (Phase 1)
=========================================
Reads .txt files with encoding detection.
Applies the same cleaning pipeline as other extractors.
"""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text from a plain text (.txt) file.
    
    Tries UTF-8 first, falls back to Latin-1 if decoding fails.
    
    Args:
        file_path: Path to the .txt file
        
    Returns:
        Cleaned text content
    """
    file_path = str(Path(file_path).resolve())
    logger.info(f"Extracting text from TXT: {file_path}")

    # Try multiple encodings
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                raw_text = f.read()
            
            cleaned = _clean_txt(raw_text)
            logger.info(
                f"Read {len(cleaned)} characters from TXT (encoding: {encoding})"
            )
            return cleaned

        except UnicodeDecodeError:
            logger.debug(f"Encoding {encoding} failed, trying next...")
            continue
        except Exception as e:
            logger.error(f"TXT extraction failed: {e}")
            return ""

    logger.error(f"Could not decode file with any supported encoding: {file_path}")
    return ""


def _clean_txt(raw_text: str) -> str:
    """Clean plain text — normalize whitespace, remove non-printable chars."""
    text = raw_text

    # Remove non-printable characters (keep standard ASCII + newlines/tabs)
    text = re.sub(r'[^\x20-\x7E\n\t]', '', text)

    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Collapse multiple spaces
    text = re.sub(r' {2,}', '  ', text)

    return text.strip()
