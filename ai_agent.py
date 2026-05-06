import json
import os
import re
from typing import Any, Dict, List

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
    intent = payload.get("intent", "")
    address = payload.get("address", "")
    phone = payload.get("phone", "")

    normalized_products: List[Dict[str, Any]] = []
    raw_products = payload.get("products", [])
    if isinstance(raw_products, list):
        for item in raw_products:
            if not isinstance(item, dict):
                continue
            normalized_products.append(
                {
                    "sku": str(item.get("sku", "")).strip(),
                    "quantity": int(item.get("quantity", 0))
                    if str(item.get("quantity", "0")).isdigit()
                    else 0,
                }
            )

    return {
        "intent": str(intent).strip(),
        "products": normalized_products,
        "address": str(address).strip(),
        "phone": str(phone).strip(),
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
        model = genai.GenerativeModel("gemini-2.5-flash")

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
      "sku": "<string>",
      "quantity": <number>
    }}
  ],
  "address": "<string>",
  "phone": "<string>"
}}
- intent değeri şu tarz niyetlerden biri olmalı: siparis_olustur, durum_sorgula, sikayet, bilgi_talebi, diger.
- products sadece SKU ve quantity içermeli, başka alan içermemeli.
- Ekstra metin, markdown veya açıklama ekleme.
"""

        response = model.generate_content(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
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
