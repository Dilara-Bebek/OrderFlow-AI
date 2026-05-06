import json
import os
import re
from typing import Any, Dict

import google.generativeai as genai


SYSTEM_PROMPT = (
    "Sen Lavora Natural adında butik bir hediyelik eşya dükkanının sipariş "
    "asistanısın. Müşteri ürün istiyorsa şu SKU'larla eşleştir: "
    "Limon Kolonyası için HEDIYE-KOLONYA-250, El Kremi için HEDIYE-KREM-50, "
    "Zeytinyağlı Sabun için HEDIYE-SABUN-1."
)


def _extract_first_json_object(text: str) -> str:
    """Return the first valid JSON object string found in model output."""
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    direct = re.search(r"\{.*\}", text, re.DOTALL)
    if direct:
        return direct.group(0)

    return text.strip()


def _normalize_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure response always includes required keys and stable types."""
    return {
        "intent": payload.get("intent", ""),
        "products": payload.get("products", []),
        "address": payload.get("address", ""),
        "phone": payload.get("phone", ""),
    }


def parse_whatsapp_message(message: str) -> Dict[str, Any]:
    """
    Parse a complex WhatsApp customer message and return structured JSON:
    {
      "intent": str,
      "products": list,
      "address": str,
      "phone": str
    }
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "intent": "error",
            "products": [],
            "address": "",
            "phone": "",
        }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
Sistem mesajı:
{SYSTEM_PROMPT}

Kullanıcı mesajı:
{message}

Görevin:
- Mesajı analiz et ve SADECE geçerli JSON döndür.
- JSON formatı mutlak suretle şöyle olmalı:
{{
  "intent": "<string>",
  "products": [
    {{
      "name": "<string>",
      "sku": "<string>",
      "quantity": <number>
    }}
  ],
  "address": "<string>",
  "phone": "<string>"
}}
- Ekstra metin, markdown veya açıklama ekleme.
"""

        response = model.generate_content(prompt)
        raw_text = (response.text or "").strip()
    except Exception:
        return {
            "intent": "error",
            "products": [],
            "address": "",
            "phone": "",
        }

    try:
        json_text = _extract_first_json_object(raw_text)
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object.")
        return _normalize_output(parsed)
    except Exception:
        return {
            "intent": "unknown",
            "products": [],
            "address": "",
            "phone": "",
        }
