"""
TX Cost Field Debugger — Streamlit App
Shows raw cost fields from TronScan API for any transaction hash.

requirements.txt:
    streamlit
    requests
"""

import json
import requests
import streamlit as st

TRONSCAN_BASE    = "https://apilist.tronscanapi.com/api"
TRONGRID_API_KEY = "ed75d57a-0ef0-462c-a068-98ccfee36883"

HEADERS = {
    "User-Agent":       "Mozilla/5.0",
    "Accept":           "application/json",
    "TRON-PRO-API-KEY": TRONGRID_API_KEY,
}

def fetch_tx(tx_hash):
    r = requests.get(
        f"{TRONSCAN_BASE}/transaction-info",
        params={"hash": tx_hash},
        headers=HEADERS,
        timeout=15
    )
    r.raise_for_status()
    return r.json()

# ── UI ────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="TX Debugger", page_icon="🔧")
st.title("🔧 Transaction Cost Field Inspector")
st.caption("Shows raw API cost fields to identify correct energy field names")

tx_hash = st.text_input(
    "Transaction Hash",
    value="8c641781c693dc12004861820c1476238b5da10cc72535cd261d128656f27012"
)

if st.button("🔍 Fetch TX Info", use_container_width=True):
    if not tx_hash.strip():
        st.error("Please enter a transaction hash.")
    else:
        with st.spinner("Fetching..."):
            try:
                data = fetch_tx(tx_hash.strip())
                cost = data.get("cost") or {}

                st.subheader("⛽ cost fields")
                st.table({"Field": list(cost.keys()), "Value": list(cost.values())})

                st.subheader("📄 Full raw response")
                st.json(data)

            except Exception as e:
                st.error(f"❌ Error: {e}")
