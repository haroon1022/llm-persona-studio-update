"""Optional OpenAI client for LLM Persona Studio.

If no API key is available, the app automatically uses a transparent demo mode
implemented in prompt_engine.demo_persona_response.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from prompt_engine import demo_persona_response

if load_dotenv:
    load_dotenv()


def get_secret(name: str, default: str = "") -> str:
    """Read from environment first; Streamlit secrets are handled in app.py."""
    return os.getenv(name, default)


def has_openai_key(api_key: Optional[str] = None) -> bool:
    key = api_key or get_secret("OPENAI_API_KEY")
    return bool(key and key.strip() and key.strip().startswith("sk-"))


def _attachment_text_context(attachments: Optional[List[Dict[str, Any]]]) -> str:
    if not attachments:
        return ""
    chunks: List[str] = []
    for item in attachments:
        text = (item.get("extracted_text") or "").strip()
        if text:
            chunks.append(f"File: {item.get('filename', 'attached document')}\n{text[:3500]}")
    if not chunks:
        return ""
    return "\n\nAttached document text available for review:\n" + "\n\n---\n\n".join(chunks)


def _image_parts(attachments: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = []
    for item in attachments or []:
        mime = str(item.get("mime_type") or "")
        path = Path(str(item.get("path") or ""))
        if not mime.startswith("image/") or not path.exists():
            continue
        try:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except Exception:
            continue
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            }
        )
    return parts[:3]


def generate_persona_reply(
    project: Dict[str, Any],
    persona: Dict[str, Any],
    user_question: str,
    history: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Return a persona response from OpenAI if configured, otherwise demo mode."""
    key = api_key or get_secret("OPENAI_API_KEY")
    selected_model = model or get_secret("OPENAI_MODEL", "gpt-4o-mini")

    attachment_context = _attachment_text_context(attachments)
    image_parts = _image_parts(attachments)
    user_prompt = user_question
    if attachment_context:
        user_prompt = f"{user_question}\n\n{attachment_context}"
    if image_parts:
        user_prompt = (
            f"{user_prompt}\n\nThe user has also attached design image(s). Review them as design material from the persona perspective."
        )

    if not has_openai_key(key) or OpenAI is None:
        response = demo_persona_response(project, persona, user_question)
        if attachments:
            response += (
                "\n\nAttachment note: attached project files are saved with this project. "
                "Live document/image-aware responses require an OpenAI API key and a vision-capable model."
            )
        return response

    client = OpenAI(api_key=key)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": persona.get("system_prompt", "")},
    ]
    for item in history or []:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})

    if image_parts:
        messages.append(
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}, *image_parts],
            }
        )
    else:
        messages.append({"role": "user", "content": user_prompt})

    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=0.4,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return (
            "Demo fallback response: I could not connect to the configured LLM service. "
            f"Technical detail: {exc}\n\n"
            + demo_persona_response(project, persona, user_question)
        )
