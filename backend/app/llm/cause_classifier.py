"""
Diagnosis Path C: LLM classifier.

Used for free-text context, behavioral signals, ambiguous cases, and
support/session context that neither Path A (decline code) nor Path B
(structured XGBoost) can resolve.

Structured output is FORCED via tool-use with an input_schema that
constrains `cause` to the exact taxonomy enum — this eliminates most
malformed-cause failures by construction, rather than hoping the model
free-forms valid JSON. The result is still run through Pydantic
(LLMDiagnosisOutput) as a second layer of defense per spec ("Validate
using Pydantic"), since a schema-constrained API doesn't guarantee the
SDK response shape is well-formed (network truncation, API version
drift, etc.).

Chain-of-thought is never surfaced: only the tool_use input block is
read. Any prose the model emits alongside the tool call is discarded,
never logged, never returned to the caller.

NOT EXERCISED against a live model in this environment — LLM_API_KEY
is not configured. See module-level docstring in app/llm/client.py.
"""
from typing import Any, Optional

import anthropic
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.taxonomy import ALL_CAUSES, Cause, DiagnosisMethod
from app.llm.client import get_llm_client
from app.schemas.diagnosis import DiagnosisResult, LLMDiagnosisOutput

logger = get_logger(__name__)

_TOOL_NAME = "emit_diagnosis"

DIAGNOSIS_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": (
        "Emit a structured cause diagnosis for a failed payment, checkout, "
        "or invoice event, given its context."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cause": {
                "type": "string",
                "enum": ALL_CAUSES,
                "description": "The single most likely cause from the fixed taxonomy.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Calibrated confidence in this diagnosis, 0 to 1.",
            },
            "reason": {
                "type": "string",
                "maxLength": 500,
                "description": "Brief, factual justification citing the specific signals used.",
            },
            "signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short list of the specific input signals that drove this diagnosis.",
            },
        },
        "required": ["cause", "confidence", "reason", "signals"],
    },
}

_SYSTEM_PROMPT = (
    "You are a payment failure diagnosis classifier for a revenue recovery "
    "system. Given structured context and free-text signals about a failed "
    "payment, checkout, or invoice, determine the single most likely cause "
    "from the fixed taxonomy provided in the tool schema. Be conservative "
    "with confidence: only report high confidence when the signals clearly "
    "and specifically support one cause over the others. You must call the "
    f"{_TOOL_NAME} tool exactly once with your diagnosis."
)


class LLMNotConfiguredError(Exception):
    pass


def _build_user_prompt(case_context: dict[str, Any]) -> str:
    lines = ["Diagnose the cause of this failed event. Context:"]
    for key, value in case_context.items():
        if value not in (None, "", []):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _extract_tool_input(response: anthropic.types.Message) -> Optional[dict]:
    for block in response.content:
        if block.type == "tool_use" and block.name == _TOOL_NAME:
            return block.input
    return None


def diagnose_llm(case_context: dict[str, Any]) -> DiagnosisResult:
    """
    Raises LLMNotConfiguredError if no API key is set — callers should
    catch this and fall back to Path B rather than crash the pipeline.
    On malformed output, retries once; on second failure, returns a
    method="llm_fallback" DiagnosisResult with cause=unknown,
    confidence=0.0 rather than raising (spec: "If still malformed:
    Fallback").
    """
    client = get_llm_client()
    if client is None:
        raise LLMNotConfiguredError("LLM_API_KEY is not configured.")

    settings = get_settings()
    if not settings.llm_model:
        raise LLMNotConfiguredError("LLM_MODEL is not configured.")

    user_prompt = _build_user_prompt(case_context)
    last_error: Optional[Exception] = None

    for attempt in (1, 2):
        try:
            response = client.messages.create(
                model=settings.llm_model,
                max_tokens=500,
                system=_SYSTEM_PROMPT,
                tools=[DIAGNOSIS_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": user_prompt}],
            )
            tool_input = _extract_tool_input(response)
            if tool_input is None:
                raise ValueError("No tool_use block found in LLM response.")

            validated = LLMDiagnosisOutput(**tool_input)
            return DiagnosisResult(
                cause=validated.cause,
                confidence=validated.confidence,
                reason=validated.reason,
                signals=validated.signals,
                method=DiagnosisMethod.LLM.value,
            )
        except (ValidationError, ValueError, KeyError, TypeError) as e:
            last_error = e
            logger.warning("LLM diagnosis attempt %d malformed: %s", attempt, e)
        except anthropic.APIError as e:
            last_error = e
            logger.warning("LLM diagnosis attempt %d API error: %s", attempt, e)

    logger.error("LLM diagnosis failed after retry; falling back. last_error=%s", last_error)
    return DiagnosisResult(
        cause=Cause.UNKNOWN.value,
        confidence=0.0,
        reason="LLM diagnosis failed validation after one retry; fell back to unknown cause.",
        signals=[],
        method="llm_fallback",
    )
