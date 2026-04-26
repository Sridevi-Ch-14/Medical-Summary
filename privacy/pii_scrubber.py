"""
ClinIQ - PII Scrubber (Privacy Layer)
========================================
Dual-strategy PII masking:
1. Primary: Microsoft Presidio (if available)
2. Fallback: Regex-based scrubber for common patterns

Masks patient names, SSN, phone, email, DOB, MRN
BEFORE any data is sent to the LLM.
"""

import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)


def scrub_pii(text: str) -> Tuple[str, List[str]]:
    """
    Remove PII from text. Returns (cleaned_text, list_of_masked_entities).
    Tries Presidio first, falls back to regex.
    """
    # Try Presidio
    try:
        return _scrub_presidio(text)
    except Exception as e:
        logger.debug(f"Presidio unavailable ({e}), using regex fallback")

    # Fallback to regex
    return _scrub_regex(text)


def _scrub_presidio(text: str) -> Tuple[str, List[str]]:
    """PII scrubbing using Microsoft Presidio."""
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    results = analyzer.analyze(
        text=text, language="en",
        entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
                  "US_SSN", "CREDIT_CARD", "DATE_TIME", "LOCATION"]
    )

    if not results:
        return text, []

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    masked_entities = [f"{r.entity_type}: '{text[r.start:r.end]}'" for r in results]

    logger.info(f"Presidio masked {len(results)} PII entities")
    return anonymized.text, masked_entities


def _scrub_regex(text: str) -> Tuple[str, List[str]]:
    """Regex-based PII scrubbing fallback."""
    masked = []
    result = text

    # Patient name patterns (after "Patient:", "Name:", "Patient Name:")
    name_patterns = [
        (r'(?i)(patient\s*(?:name)?[\s:]+)([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
         r'\1[REDACTED_NAME]'),
        (r'(?i)(name[\s:]+)([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
         r'\1[REDACTED_NAME]'),
    ]

    for pattern, replacement in name_patterns:
        matches = re.findall(pattern, result)
        for match in matches:
            if isinstance(match, tuple) and len(match) > 1:
                masked.append(f"NAME: '{match[1]}'")
        result = re.sub(pattern, replacement, result)

    # SSN: XXX-XX-XXXX
    ssn_pattern = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    ssn_matches = re.findall(ssn_pattern, result)
    for m in ssn_matches:
        masked.append(f"SSN: '{m}'")
    result = re.sub(ssn_pattern, '[REDACTED_SSN]', result)

    # Phone numbers
    phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    phone_matches = re.findall(phone_pattern, result)
    for m in phone_matches:
        masked.append(f"PHONE: '{m}'")
    result = re.sub(phone_pattern, '[REDACTED_PHONE]', result)

    # Email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_matches = re.findall(email_pattern, result)
    for m in email_matches:
        masked.append(f"EMAIL: '{m}'")
    result = re.sub(email_pattern, '[REDACTED_EMAIL]', result)

    # DOB patterns
    dob_patterns = [
        (r'(?i)((?:date of birth|dob|d\.o\.b\.|birth\s*date)[\s:]+)(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
         r'\1[REDACTED_DOB]'),
        (r'(?i)((?:date of birth|dob|d\.o\.b\.)[\s:]+)([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
         r'\1[REDACTED_DOB]'),
    ]
    for pattern, replacement in dob_patterns:
        matches = re.findall(pattern, result)
        for match in matches:
            if isinstance(match, tuple) and len(match) > 1:
                masked.append(f"DOB: '{match[1]}'")
        result = re.sub(pattern, replacement, result)

    # MRN (Medical Record Number)
    mrn_pattern = r'(?i)((?:mrn|medical record|record\s*#?)[\s:#]+)(\w+[-]?\d+)'
    mrn_matches = re.findall(mrn_pattern, result)
    for m in mrn_matches:
        if isinstance(m, tuple) and len(m) > 1:
            masked.append(f"MRN: '{m[1]}'")
    result = re.sub(mrn_pattern, r'\1[REDACTED_MRN]', result)

    if masked:
        logger.info(f"Regex PII scrubber masked {len(masked)} entities")

    return result, masked
