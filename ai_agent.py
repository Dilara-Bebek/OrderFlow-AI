import json
import os
import re
from typing import Any, Dict, List

from google import genai

# Lavora Natural marka kimligi ve SKU tanimlamalari
SYSTEM_PROMPT = (
    "Sen Lavora Natural adında butik bir hediyelik eşya dükkanının sipariş "
    "asistanısın. Müşteri ürün istiyorsa şu SKU'larla eşleştir: "
    "Limon Kolonyası için HEDIYE-KOLONYA-250, El Kremi için HEDIYE-KREM-50, "
    "Sabun için HEDIYE-SABUN-1."
)


def _extract_first_json_object(text: str) -> str:
    """Model ciktisi icindeki ilk gecerli JSON objesini bulur."""
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    direct = re.search(r"\{.*\}", text, re.DOTALL)
    if direct:
        return direct.group(0)

    return text.strip()


def _normalize_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    """JSON anahtarlarinin ve veri tiplerinin kararli olmasini saglar."""
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
    Karmasik WhatsApp mesajini analiz eder ve yapilandirilmis JSON doner.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "intent": "error",
            "message": "GEMINI_API_KEY bulunamadi. Ortam degiskenini tanimlayin.",
            "products": [],
            "address": "",
            "phone": "",
        }

    try:
        # Modern SDK (google-genai) istemcisi API surum uyumlulugunu otomatik yonetir.
        client = genai.Client(api_key=api_key)

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
- intent değeri: siparis_olustur, durum_sorgula, sikayet, bilgi_talebi veya diger olmalı.
- products sadece SKU ve quantity içermeli.
- Ekstra metin veya açıklama ekleme.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        raw_text = (getattr(response, "text", "") or "").strip()
    except Exception as e:
        return {
            "intent": "error",
            "error_detail": str(e),
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

if __name__ == "__main__":
    sample_message = (
        "Merhabalar Lavora Natural ekibi! Ben Isparta'dan arıyorum. "
        "Annem için 3 adet limon kolonyası ve kendime de 1 tane sabun "
        "almak istiyorum. Adresim: Çünür Mahallesi, 102. Cadde No:5. "
        "Telefonum: 05051234567. Yarın kargoya verebilir misiniz?"
    )

    print("\n" + "=" * 56)
    print("Lavora Natural WhatsApp Mesaj Analizi")
    print("=" * 56)
    result = parse_whatsapp_message(sample_message)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 56 + "\n")