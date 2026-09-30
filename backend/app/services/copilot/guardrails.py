"""Guardrails System — enforce safety and quality rules on responses."""

import re
from typing import Dict, Any

from app.services.copilot.state import CopilotState

STANDARD_DISCLAIMER = (
    "\n\n---\n*This analysis is informational only and does not constitute financial advice. "
    "Past performance does not guarantee future results. Consult a qualified financial "
    "advisor before making investment decisions.*"
)

# Guardrail patterns
FINANCIAL_ADVICE_PATTERNS = [
    r"\byou should buy\b",
    r"\byou should sell\b",
    r"\bI recommend buying\b",
    r"\bI recommend selling\b",
    r"\bbuy .+ stock\b",
    r"\bsell .+ stock\b",
    r"\bstrongly recommend\b.*\b(buy|sell)\b",
    r"\badd .+ to your portfolio\b",
    r"\bremove .+ from your portfolio\b",
]

GUARANTEE_PATTERNS = [
    r"\bwill definitely\b",
    r"\bguaranteed\b",
    r"\bcertain to\b",
    r"\bwill increase\b",
    r"\bwill decrease\b",
    r"\bwill outperform\b",
    r"\bwill underperform\b",
    r"\bno risk\b",
    r"\brisk[- ]?free\b",
]

MISSING_CITATION_PATTERNS = [
    r"\b\d+\.?\d*%\b",  # Percentages
    r"\b\d+\.?\d*x\b",  # Multiples
    r"\$[\d,]+\.?\d*",  # Dollar amounts
    r"\bSharpe\b.*\d+\.?\d*",  # Sharpe ratio values
    r"\bVolatility\b.*\d+\.?\d*%",  # Volatility values
    r"\bBeta\b.*\d+\.?\d*",  # Beta values
]


def check_financial_advice(text: str) -> list[str]:
    """Check for financial advice language."""
    flags = []
    for pattern in FINANCIAL_ADVICE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append("financial_advice_detected")
            break
    return flags


def check_guarantees(text: str) -> list[str]:
    """Check for guarantee language."""
    flags = []
    for pattern in GUARANTEE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append("guarantee_language_detected")
            break
    return flags


def check_citations(text: str, citations: list) -> list[str]:
    """Check if numerical claims have citations."""
    flags = []
    cited_sources = set()
    for c in citations:
        cited_sources.add(c.get("source", ""))
    
    # Simple check: if text has numbers but no citations
    has_numbers = any(re.search(p, text) for p in MISSING_CITATION_PATTERNS)
    if has_numbers and not citations:
        flags.append("missing_citations")
    return flags


def sanitize_financial_advice(text: str) -> str:
    """Replace financial advice language with softer alternatives."""
    replacements = [
        (r"\byou should buy\b", "analysis suggests considering adding"),
        (r"\byou should sell\b", "analysis suggests considering reducing"),
        (r"\bI recommend buying\b", "analysis indicates potential merit in"),
        (r"\bI recommend selling\b", "analysis indicates potential merit in reducing"),
        (r"\bstrongly recommend\b.*\b(buy|sell)\b", "analysis suggests"),
        (r"\badd .+ to your portfolio\b", "consider adding to the portfolio"),
        (r"\bremove .+ from your portfolio\b", "consider reducing exposure to"),
    ]
    
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def sanitize_guarantees(text: str) -> str:
    """Soften guarantee language."""
    replacements = [
        (r"\bwill definitely\b", "is likely to"),
        (r"\bguaranteed\b", "highly probable"),
        (r"\bcertain to\b", "very likely to"),
        (r"\bwill increase\b", "may increase"),
        (r"\bwill decrease\b", "may decrease"),
        (r"\bwill outperform\b", "may outperform"),
        (r"\bwill underperform\b", "may underperform"),
        (r"\bno risk\b", "minimal risk"),
        (r"\brisk[- ]?free\b", "low-risk"),
    ]
    
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def ensure_disclaimer(text: str) -> str:
    """Ensure standard disclaimer is present."""
    if STANDARD_DISCLAIMER not in text:
        return text + STANDARD_DISCLAIMER
    return text


async def guardrails_node(state: CopilotState) -> CopilotState:
    """Apply guardrails to the synthesized response."""
    
    response = state.get("final_response", "")
    citations = state.get("citations", [])
    flags = state.get("guardrail_flags", [])
    
    # Check and sanitize
    flags.extend(check_financial_advice(response))
    flags.extend(check_guarantees(response))
    flags.extend(check_citations(response, citations))
    
    # Apply sanitization
    response = sanitize_financial_advice(response)
    response = sanitize_guarantees(response)
    response = ensure_disclaimer(response)
    
    return {
        **state,
        "final_response": response,
        "guardrail_flags": list(set(flags)),  # Deduplicate
    }