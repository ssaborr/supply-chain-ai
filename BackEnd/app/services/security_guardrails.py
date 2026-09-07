"""
MLSecOps & AI Security Guardrails
Aligns with OWASP Top 10 for LLMs (LLM01: Prompt Injection, LLM06: Excessive Agency).
Provides input sanitization, jailbreak detection, and strict tool execution boundaries.
"""

import re
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("security_guardrails")

# Maximum permitted character length for user chat prompts to prevent context stuffing
MAX_PROMPT_LENGTH = 1500

# Known Prompt Injection and Jailbreak signatures
PROMPT_INJECTION_PATTERNS = [
    # Instruction override attempts
    r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules|commands)\b",
    r"(?i)\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)\b",
    r"(?i)\bforget\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)\b",
    # System role hijacking & jailbreaks
    r"(?i)\b(?:system\s+override|admin\s+override|developer\s+mode|jailbreak|dan\s+mode)\b",
    r"(?i)\byou\s+are\s+now\s+(?:an?\s+unfiltered|dan|root|god\s+mode)\b",
    r"(?i)\bact\s+as\s+(?:an?\s+unrestricted|a\s+malicious|dan)\b",
    # Prompt leak & system prompt extraction
    r"(?i)\b(?:repeat|print|reveal|output|show)\s+(?:the\s+)?(?:system\s+prompt|initial\s+prompt|instructions\s+verbatim)\b",
    r"(?i)\bwhat\s+are\s+your\s+(?:exact\s+)?system\s+instructions\b",
    # Dangerous tool injection triggers
    r"(?i)db_query\s*:\s*\{.*(?:drop|delete|update|insert|\$where).*\}"
]

# Strictly allowed collections for the Chatbot MCP tool
# Notice: 'admin' is explicitly EXCLUDED to prevent credential/hash exfiltration
ALLOWED_ADMIN_COLLECTIONS = {
    "sales_orders", "anomalies", "products", "client", 
    "kpis", "purchases", "departments", "insights", "forecasts"
}

ALLOWED_SUPPLIER_COLLECTIONS = {
    "sales_orders", "anomalies", "products"
}

ALLOWED_OPERATIONS = {"find_one", "find_many", "find", "count", "aggregate"}

# Disallowed Mongo operators that can cause arbitrary JS execution or resource exhaustion
FORBIDDEN_OPERATORS = {"$where", "$function", "$accumulator", "$expr"}


def sanitize_and_validate_prompt(message: str, language: str = "en") -> Tuple[bool, Optional[str]]:
    """
    Validates user prompt against length violations and prompt injection / jailbreak patterns.
    
    Returns:
        (is_safe: bool, rejection_message: Optional[str])
    """
    if not message or not message.strip():
        err = "Message cannot be empty." if language != "fr" else "Le message ne peut pas être vide."
        return False, err

    # 1. Length Check (Denial of Service & Context Stuffing)
    if len(message) > MAX_PROMPT_LENGTH:
        logger.warning(f"Security Alert: Prompt exceeded maximum allowed length ({len(message)} chars)")
        err = (
            f"Security Policy: Your message exceeds the maximum allowed length of {MAX_PROMPT_LENGTH} characters."
            if language != "fr"
            else f"Politique de sécurité : Votre message dépasse la longueur maximale autorisée ({MAX_PROMPT_LENGTH} caractères)."
        )
        return False, err

    # 2. Check for Prompt Injection / Jailbreak Signatures
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, message):
            logger.warning(f"MLSecOps Alert: Prompt injection attempt detected matching pattern '{pattern}'")
            err = (
                "[Security Alert - OWASP LLM01]: Prompt injection or unauthorized instruction override detected. Your request has been blocked."
                if language != "fr"
                else "[Alerte Sécurité - OWASP LLM01] : Tentative d'injection de prompt ou de contournement détectée. Votre requête a été bloquée."
            )
            return False, err

    return True, None


def validate_db_tool_call(query_obj: Dict[str, Any], is_supplier: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Enforces the Principle of Least Privilege for LLM Database Tool Calling.
    Prevents unauthorized collection access (e.g., admin credential tables)
    and blocks dangerous write/JS operations.
    
    Returns:
        (is_valid: bool, error_reason: Optional[str])
    """
    if not isinstance(query_obj, dict):
        return False, "Invalid query format: Must be a JSON object."

    collection = query_obj.get("collection")
    operation = query_obj.get("operation", "find_one")
    db_filter = query_obj.get("filter", {})
    pipeline = query_obj.get("pipeline", [])

    # 1. Collection Access Control (RBAC)
    allowed_collections = ALLOWED_SUPPLIER_COLLECTIONS if is_supplier else ALLOWED_ADMIN_COLLECTIONS
    if collection not in allowed_collections:
        logger.warning(f"MLSecOps Alert: Blocked unauthorized database tool access to collection '{collection}'")
        return False, f"Access Denied: Collection '{collection}' is not accessible via AI Assistant tools."

    # 2. Operation Validation (Read-Only Enforcement)
    if operation not in ALLOWED_OPERATIONS:
        logger.warning(f"MLSecOps Alert: Blocked non-read operation '{operation}' via AI tool")
        return False, f"Access Denied: Operation '{operation}' is prohibited. Only read queries are allowed."

    # 3. Check for dangerous Mongo operators ($where, $function)
    query_str = str(db_filter) + str(pipeline)
    for forbidden in FORBIDDEN_OPERATORS:
        if forbidden in query_str:
            logger.warning(f"MLSecOps Alert: Blocked dangerous NoSQL operator '{forbidden}' in AI tool call")
            return False, f"Access Denied: Dangerous operator '{forbidden}' is strictly blocked."

    return True, None


def validate_email_recipient(to_email: str) -> bool:
    """
    Validates that automated email notifications are dispatched only to valid email addresses.
    Prevents excessive agency attacks and email header injection.
    """
    if not to_email or "\n" in to_email or "\r" in to_email:
        return False
    
    email_regex = r"^[\w\.\+\-]+@(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}$"
    return bool(re.match(email_regex, to_email.strip()))
