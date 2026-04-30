import requests
import streamlit as st

from app.core.config import settings

API_BASE = "http://127.0.0.1:8000/api"


st.set_page_config(page_title=settings.streamlit_title, layout="wide")
st.title("CompetitorRecognition")
st.caption("Agentic web intelligence platform for discovery, extraction, and relationship-aware analysis.")

with st.sidebar:
    st.header("Run Capture")
    niche = st.text_input("Niche", value="AI sales tooling")
    query = st.text_area("Search query", value="AI sales tooling competitors funding pricing partnerships")
    max_results = st.slider("Search results", min_value=3, max_value=20, value=8)
    run_button = st.button("Run intelligence capture")

if run_button:
    response = requests.post(
        f"{API_BASE}/intelligence/runs",
        json={"niche": niche, "query": query, "max_results": max_results},
        timeout=120,
    )
    response.raise_for_status()
    st.success("Capture finished")
    st.json(response.json())

st.header("Relationship-aware Query")
query_text = st.text_input("Ask the indexed intelligence graph", value="pricing partnerships")
if st.button("Run query"):
    response = requests.post(
        f"{API_BASE}/intelligence/query",
        json={"query": query_text, "limit": 5},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    st.subheader("Answer")
    st.write(payload["answer"])
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Vector hits")
        st.json(payload["vector_hits"])
    with col2:
        st.subheader("Graph hits")
        st.json(payload["graph_hits"])

st.header("Recent Runs")
recent = requests.get(f"{API_BASE}/intelligence/runs", timeout=30)
if recent.ok:
    for item in recent.json()[:5]:
        with st.expander(f"Run #{item['id']} | {item['niche']} | {item['status']}"):
            st.write(item["summary"])
            st.write(
                {
                    "sources": item["source_count"],
                    "documents": item["document_count"],
                    "entities": item["entity_count"],
                    "relations": item["relation_count"],
                }
            )
