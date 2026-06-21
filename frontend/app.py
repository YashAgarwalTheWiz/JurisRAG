import streamlit as st
import requests

API_URL = "http://localhost:8000/query"

st.set_page_config(page_title="JurisRAG", page_icon="⚖️")
st.title("⚖️ JurisRAG — Indian Case Law Research Assistant")
st.caption("GraphRAG over Indian Supreme Court judgments — combines semantic search with structured graph queries.")

# st.session_state persists values across reruns. Streamlit reruns the
# ENTIRE script top-to-bottom on every interaction (every button click,
# every text input change) — without session_state, anything you stored
# in a normal Python variable would just reset each time. Here it's used
# to keep the conversation visible after the rerun triggered by clicking
# "Ask".
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: query, answer, debug_log

query = st.text_input("Ask a question about Indian case law:", placeholder="e.g. Which cases invoke Section 302 IPC?")

if st.button("Ask") and query.strip():
    with st.spinner("Retrieving and reasoning over case law..."):
        try:
            response = requests.post(API_URL, json={"query": query}, timeout=60)
            response.raise_for_status()
            data = response.json()
            st.session_state.history.append({
                "query": query,
                "answer": data["answer"],
                "debug_log": data.get("debug_log", []),
            })
        except requests.exceptions.ConnectionError:
            st.error("Can't reach the backend. Is `uvicorn api.main:app` running on port 8000?")
        except requests.exceptions.HTTPError as e:
            st.error(f"Backend returned an error: {e}")

# Show most recent first
for record in reversed(st.session_state.history):
    st.markdown(f"**Q: {record['query']}**")
    st.markdown(record["answer"])
    if record["debug_log"]:
        with st.expander("Debug info"):
            st.dataframe(record["debug_log"])
    st.divider()