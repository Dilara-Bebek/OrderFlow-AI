from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Literal

import google.generativeai as genai
import pandas as pd
import streamlit as st
from dotenv import load_dotenv


Role = Literal["user", "assistant"]
Page = Literal["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"]

SYSTEM_PROMPT = (
    "Sen bir Hediyelik Eşya ve Kozmetik Dükkanının akıllı WhatsApp sipariş asistanı "
    "OrderFlow AI'sın. Müşteriyle çok doğal, kısa ve kibar bir dille konuş. "
    "Müşteri sipariş verdiğinde niyeti anla, ürünleri teyit et ve siparişi aldığına dair bir cevap dön."
)


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def configure_gemini() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. Proje köküne .env ekleyip GEMINI_API_KEY=... tanımlayın."
        )
    genai.configure(api_key=api_key)


@st.cache_resource(show_spinner=False)
def get_model() -> Any:
    configure_gemini()
    model = genai.GenerativeModel("gemini-pro")
    try:
        return genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_PROMPT)
    except TypeError:
        return genai.GenerativeModel(model_name=model_name)


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Merhaba! Ben OrderFlow AI.\n\n"
                    "Sipariş vermek istediğiniz ürünleri yazabilirsiniz. "
                    "Ornek: 2 limon kolonyasi, 1 el kremi."
                ),
                "ts": now_ts(),
            }
        ]


def to_gemini_history(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for message in messages:
        role: Role = message["role"]  # type: ignore[assignment]
        gemini_role = "user" if role == "user" else "model"
        history.append({"role": gemini_role, "parts": [message["content"]]})
    return history


def generate_reply(user_text: str, messages: list[dict[str, str]]) -> str:
    model = get_model()
    history = to_gemini_history(messages[:-1])
    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_text)
        text = getattr(response, "text", "")
        return str(text).strip() if text else "Su an yanit uretemedim. Lutfen tekrar deneyin."
    except Exception:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Asagidaki musteri mesajina uygun bir yanit uret:\n"
            f"{user_text}"
        )
        response = model.generate_content(prompt)
        text = getattr(response, "text", "")
        return str(text).strip() if text else "Su an yanit uretemedim. Lutfen tekrar deneyin."


def render_sidebar() -> Page:
    st.sidebar.title("OrderFlow AI")
    st.sidebar.caption("Hediyelik Esya & Kozmetik")
    page: Page = st.sidebar.radio(
        "Menu",
        options=["💬 WhatsApp Simülasyonu", "📊 Admin Dashboard"],
        index=0,
    )
    st.sidebar.divider()
    st.sidebar.info("Yapilandirma: .env -> GEMINI_API_KEY")
    return page


def render_whatsapp_page() -> None:
    st.title("💬 WhatsApp Simülasyonu")
    st.caption("Musteri ile gercek zamanli chat akisı (Gemini destekli)")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            st.caption(message["ts"])

    user_text = st.chat_input("Mesajinizi yazin...")
    if not user_text:
        return

    st.session_state.messages.append({"role": "user", "content": user_text, "ts": now_ts()})

    with st.chat_message("assistant"):
        with st.spinner("Yanit hazirlaniyor..."):
            try:
                reply = generate_reply(user_text, st.session_state.messages)
            except Exception as exc:
                reply = f"Konfigurasyon/baglanti hatasi: {exc}"
        st.markdown(reply)
        st.caption(now_ts())

    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": now_ts()})
    st.rerun()


def render_admin_dashboard_page() -> None:
    st.title("📊 Admin Dashboard")
    st.caption("Statik (mock) siparis gorunumu")

    mock_orders = [
        {"Siparis No": "#1042", "Musteri": "Ayse Yilmaz", "Durum": "Bekleyen", "Tutar (TL)": 228.0},
        {"Siparis No": "#1041", "Musteri": "Mehmet Kaya", "Durum": "Hazirlaniyor", "Tutar (TL)": 89.0},
        {"Siparis No": "#1040", "Musteri": "Elif Demir", "Durum": "Tamamlandi", "Tutar (TL)": 347.0},
        {"Siparis No": "#1039", "Musteri": "Can Arslan", "Durum": "Bekleyen", "Tutar (TL)": 128.0},
    ]
    df = pd.DataFrame(mock_orders)

    total_orders = len(df)
    waiting_orders = int((df["Durum"] == "Bekleyen").sum())
    completed_orders = int((df["Durum"] == "Tamamlandi").sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Siparis", f"{total_orders}")
    c2.metric("Bekleyen", f"{waiting_orders}")
    c3.metric("Tamamlanan", f"{completed_orders}")

    st.divider()
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Siparis No": st.column_config.TextColumn(),
            "Musteri": st.column_config.TextColumn(),
            "Durum": st.column_config.TextColumn(),
            "Tutar (TL)": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def main() -> None:
    st.set_page_config(
        page_title="OrderFlow AI - Hediyelik Esya & Kozmetik",
        page_icon="🧴",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ensure_session_state()

    page = render_sidebar()
    if page == "💬 WhatsApp Simülasyonu":
        render_whatsapp_page()
    else:
        render_admin_dashboard_page()


if __name__ == "__main__":
    main()
