"""
Prompt builders for answer generation.
"""

from __future__ import annotations


def route_system_prompt() -> str:
    """
    Route each user message to either casual chat or RAG.
    """
    return (
        "You are a classifier for a RAG chatbot.\n"
        "Return ONLY valid JSON with this exact schema: {\"route\":\"casual\"} or {\"route\":\"rag\"}.\n"
        "Never use any emoji.\n"
        "Use \"casual\" for small talk, greetings, thanks, jokes, assistant meta chat, and conversation-memory questions.\n"
        "Conversation-memory questions include requests about prior chat turns or personal details shared in chat "
        "(for example: \"what is my name\", \"what did I ask before\", \"summarize our chat\").\n"
        "Use \"rag\" for questions that likely need external knowledge lookup or document grounding.\n"
        "If uncertain, choose \"rag\"."
    )


def route_user_prompt(question: str, recent_history: str) -> str:
    return (
        "Recent conversation history (most recent last):\n"
        f"{recent_history}\n\n"
        "Current user message:\n"
        f"{question}\n\n"
        "Return only the required JSON and never use any emoji."
    )


def casual_system_prompt() -> str:
    """
    System prompt for non-RAG casual chat turns.
    """
    return (
        "You are a helpful assistant.\n"
        "For casual conversation, reply naturally and concisely.\n"
        "Never use any emoji.\n"
        "If asked about user-specific details (name, preferences, previous statements), use only conversation history.\n"
        "If that detail is not present in conversation history, say you do not know yet.\n"
        "Do not mention retrieval or citations unless the user asks."
    )


def system_prompt() -> str:
    """
    Keep answers grounded in retrieved context.
    """
    return (
        "You are a retrieval-grounded assistant.\n"
        "Answer only from the provided context.\n"
        "Never use any emoji.\n"
        "If the context is insufficient, say you do not have enough information.\n"
        "Do NOT mention sources, or phrases like 'according to S3' in the answer text.\n"
        "The API will attach sources separately.\n"
        "Do not invent facts."
    )


def user_prompt(question: str, context_block: str) -> str:
    return (
        f"Question:\n{question}\n\n"
        "Context chunks:\n"
        f"{context_block}\n\n"
        "Return a concise answer without inline source-id citations. Never use any emoji."
    )
