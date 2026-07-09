import json
from io import StringIO
from pathlib import Path

import streamlit as st

from src.complaint_rag import ComplaintRAG, build_demo_dataset


DATA_DIR = Path("data/complaints")


@st.cache_resource
def load_rag():
    if not DATA_DIR.exists() or not any(DATA_DIR.glob("*.json")):
        build_demo_dataset(DATA_DIR, count=200)
    return ComplaintRAG(DATA_DIR, top_k=5)


st.set_page_config(page_title="Customer Complaint Q&A Bot", page_icon="💬")
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #0f172a, #1e293b); color: white; }
    .block-container { padding-top: 1.3rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💬 Customer Complaint Q&A Bot")
st.caption("Ask about complaints and resolve them with evidence from your support knowledge base.")

rag = load_rag()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! I can help find similar complaints and suggest likely resolutions. Try asking about billing, refunds, delivery, subscriptions, or product defects.",
        }
    ]

with st.sidebar:
    st.header("Knowledge base")
    st.write(f"Loaded {len(rag.records)} complaint records")
    st.write("You can use the built-in demo dataset or upload your own JSON file with complaint/solution records.")

    uploaded_file = st.file_uploader("Upload complaint JSON", type=["json"])
    if uploaded_file is not None:
        try:
            payload = json.load(StringIO(uploaded_file.getvalue().decode("utf-8")))
            if isinstance(payload, dict):
                payload = [payload]
            if not payload:
                st.error("The uploaded file contains no records.")
            else:
                rag = ComplaintRAG(records=payload, top_k=5)
                st.success(f"Loaded {len(rag.records)} records from {uploaded_file.name}")
        except Exception as exc:
            st.error(f"Upload failed: {exc}")

    if st.button("Refresh demo data"):
        build_demo_dataset(DATA_DIR, count=200)
        st.cache_resource.clear()
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask a question about customer complaints")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching related complaints..."):
            result = rag.answer(prompt)
        st.markdown(result["answer"])
        if result["sources"]:
            with st.expander("Relevant sources"):
                for source in result["sources"]:
                    st.write(f"- {source}")

    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
