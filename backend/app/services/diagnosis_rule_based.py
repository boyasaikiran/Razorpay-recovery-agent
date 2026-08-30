"""
Diagnosis Path A: deterministic rule-based decline-code mapper.

Handles structured payment failures where decline_code is present and
recognized. No probability, no model — a direct lookup.
"""
from typing import Optional

from app.core.decline_code_mapping import RULE_BASED_CONFIDENCE, RULE_BASED_DECLINE_CODE_MAP
from app.core.taxonomy import DiagnosisMethod
from app.schemas.diagnosis import DiagnosisResult


def diagnose_rule_based(decline_code: Optional[str]) -> Optional[DiagnosisResult]:
    """
    Returns a DiagnosisResult if decline_code is present and mapped,
    else None (signals the caller to fall through to Path B/C).
    """
    if not decline_code:
        return None

    cause = RULE_BASED_DECLINE_CODE_MAP.get(decline_code)
    if cause is None:
        return None

    return DiagnosisResult(
        cause=cause,
        confidence=RULE_BASED_CONFIDENCE,
        reason=f"decline_code '{decline_code}' matched a known rule-based mapping.",
        signals=[decline_code],
        method=DiagnosisMethod.RULE_BASED.value,
    )
