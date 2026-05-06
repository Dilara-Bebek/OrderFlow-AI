from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


SYSTEM_PROMPT = """
Sen bir kozmetik ve hediyelik esya dukkaninin WhatsApp siparis asistani "OrderFlow AI"sin.
Musteriyle dogal, kibar ve kisa konus.

Kurallar:
1) Siparisin tamamlanmasi icin 5 bilgi kesinlikle sarttir:
   - customer_name (ad-soyad)
   - urun(ler)
   - miktar(lar)
   - acik adres
   - sehir
   Bu 5 alandan biri eksikse ASLA siparisi tamamlama.

2) Eksik bilgi kontrolu:
   - Sadece eksik olan bilgiyi sor.
   - Ornek:
     "Adiniza kayit acabilmem icin isminizi ve soyisminizi ogrenebilir miyim?"
     "Hangi sehre gonderecegiz?"
   - Bilgiler tamamlanmadan JSON uretme.

3) Sepet mantigi:
   - Musteri ayni anda birden fazla urun isteyebilir.
   - Tum urunleri ve miktarlari hafizada tut.
   - Katalog:
     ["Limon Kolonyasi", "Gul Kremi", "Zeytinyagli Sabun", "Gul Suyu"]
   - Fuzzy matching uygula:
     "isparta gulu", "gul krem", "gul kremi" -> "Gul Kremi"
   - Dogal dilden miktar cikar:
     "1 gul kremi", "iki sabun", "100 kolonya"

4) Onay asamasi (cok kritik):
   - Tum 5 bilgi tamamlandiginda HEMEN JSON URETME.
   - Once "Siparis Ozeti" ver:
     - ad-soyad
     - sehir
     - acik adres
     - tum urunler ve miktarlar
   - Ardindan acikca sor:
     "Siparisinizi onayliyor musunuz?"

5) JSON uretim kurali:
   - Sadece musteri "Evet", "Onayliyorum", "Onay" gibi kesin onay verirse JSON uret.
   - JSON disinda hicbir metin ekleme.
   - Cikti semasi:
{
  "status": "complete",
  "data": {
    "customer_name": "Ahmet Yilmaz",
    "city": "Isparta",
    "address": "Karaoz Mah. Hasan Namal Cad. No: 74",
    "items": [
      {"product_name": "Limon Kolonyasi", "quantity": 100},
      {"product_name": "Zeytinyagli Sabun", "quantity": 20}
    ]
  }
}
""".strip()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
        return
    except Exception:
        pass

    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@st.cache_resource(show_spinner=False)
def get_gemini_model() -> Any:
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY bulunamadi. Lutfen .env dosyasini kontrol edin.")

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-generativeai kutuphanesi bulunamadi. Kurulum: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        return genai.GenerativeModel(model_name=model_name)


def ensure_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Merhaba, ben OrderFlow AI. Siparisinizi olusturmak icin yardimci olayim. "
                    "Urun, miktar ve mumkunse adresinizi yazabilirsiniz."
                ),
                "ts": now_ts(),
            }
        ]
    if "last_complete_order" not in st.session_state:
        st.session_state.last_complete_order = None


def render_admin_dashboard() -> None:
    st.title("Gelen Siparisler")
    db_path = "orderflow_ai.db"

    if not os.path.exists(db_path):
        st.info("Henüz sipariş bulunmamaktadır.")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            table_check = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'",
                conn,
            )
            if table_check.empty:
                st.info("Henüz sipariş bulunmamaktadır.")
                return

            df = pd.read_sql_query("SELECT * FROM orders", conn)
    except Exception:
        st.info("Henüz sipariş bulunmamaktadır.")
        return

    if df.empty:
        st.info("Henüz sipariş bulunmamaktadır.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)


def apply_whatsapp_css() -> None:
    st.markdown(
        """
<style>
div[data-testid="stChatMessage"] {
    border-radius: 14px;
    padding: 0.35rem 0.2rem;
}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) {
    background-color: #e9f8ea;
    border: 1px solid #d5ebd6;
}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
    background-color: #ffffff;
    border: 1px solid #e8e8e8;
}
</style>
""",
        unsafe_allow_html=True,
    )


def to_gemini_history(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})
    return history


def gemini_reply(user_text: str, messages: list[dict[str, str]]) -> str:
    model = get_gemini_model()
    history = to_gemini_history(messages[:-1])

    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_text)
        text = getattr(response, "text", None)
        return str(text).strip() if text else ""
    except Exception:
        prompt = f"{SYSTEM_PROMPT}\n\nMusteri mesaji:\n{user_text}"
        response = model.generate_content(prompt)
        text = getattr(response, "text", None)
        return str(text).strip() if text else ""


def parse_complete_order_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        payload = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("status") != "complete":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    customer_name = data.get("customer_name")
    city = data.get("city")
    address = data.get("address")
    items = data.get("items")

    if not isinstance(customer_name, str) or not customer_name.strip():
        return None
    if not isinstance(city, str) or not city.strip():
        return None
    if not isinstance(address, str) or not address.strip():
        return None
    if not isinstance(items, list) or not items:
        return None
    for item in items:
        if not isinstance(item, dict):
            return None
        product_name = item.get("product_name")
        quantity = item.get("quantity")
        if not isinstance(product_name, str) or not product_name.strip():
            return None
        if not isinstance(quantity, int) or quantity <= 0:
            return None

    return payload


def render_chat() -> None:
    st.title("OrderFlow AI - WhatsApp Business Simulasyonu")
    st.caption("Gemini destekli siparis asistani")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            st.caption(msg["ts"])

    user_text = st.chat_input("Mesajinizi yazin...")
    if not user_text:
        if st.session_state.last_complete_order:
            st.success("✅ Siparis basariyla veritabanina iletilecek formata cevrildi!")
            st.json(st.session_state.last_complete_order)
        return

    st.session_state.messages.append({"role": "user", "content": user_text, "ts": now_ts()})

    with st.chat_message("user"):
        st.markdown(user_text)
        st.caption(st.session_state.messages[-1]["ts"])

    with st.spinner("OrderFlow AI yaziyor..."):
        try:
            reply = gemini_reply(user_text, st.session_state.messages)
        except Exception as exc:
            reply = f"Sistem hatasi: {exc}"

    parsed = parse_complete_order_json(reply)
    if parsed is not None:
        st.session_state.last_complete_order = parsed
        st.success("✅ Siparis basariyla veritabanina iletilecek formata cevrildi!")
        st.json(parsed)
        return

    if not reply:
        reply = "Siparisinizi aliyorum, devam etmek icin bilgileri biraz daha detaylandirabilir misiniz?"

    with st.chat_message("assistant"):
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": now_ts()})


def main() -> None:
    st.set_page_config(page_title="OrderFlow AI", page_icon="💬", layout="centered")
    ensure_state()
    apply_whatsapp_css()
    page = st.sidebar.radio("Menu", ["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"], index=0)

    if page == "📊 Admin Dashboard":
        render_admin_dashboard()
    else:
        render_chat()


if __name__ == "__main__":
    main()
