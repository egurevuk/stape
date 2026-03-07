"""
USDT TRC-20 Outgoing Wallet Screener — Streamlit Web App

Requirements (save as requirements.txt in same folder):
    streamlit
    requests
    pandas
"""

import time
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
USDT_CONTRACT        = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID_API_KEY     = "ed75d57a-0ef0-462c-a068-98ccfee36883"
TRONSCAN_BASE        = "https://apilist.tronscanapi.com/api"
ENERGY_UNIT_PRICE_SUN = 420
MAX_TX               = 2000
DELAY                = 0.2

HEADERS = {
    "User-Agent":       "Mozilla/5.0",
    "Accept":           "application/json",
    "TRON-PRO-API-KEY": TRONGRID_API_KEY,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def get(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_outgoing(wallet, ts_start, ts_end, progress_bar, status_text):
    txs, start, limit = [], 0, 50
    total = None

    while True:
        params = {
            "limit":            limit,
            "start":            start,
            "relatedAddress":   wallet,
            "contract_address": USDT_CONTRACT,
            "start_timestamp":  ts_start,
            "end_timestamp":    ts_end,
            "db_version":       1,
        }
        data  = get(f"{TRONSCAN_BASE}/token_trc20/transfers", params)
        items = data.get("token_transfers") or data.get("data") or []

        if total is None:
            total = data.get("total") or data.get("rangeTotal") or len(items)

        for t in items:
            from_addr = t.get("from_address") or t.get("transferFromAddress", "")
            if from_addr.lower() != wallet.lower():
                continue
            txs.append({
                "tx_hash":   t.get("transaction_id") or t.get("transactionHash", ""),
                "timestamp": t.get("block_ts") or t.get("blockTimestamp") or 0,
                "to_addr":   t.get("to_address") or t.get("transferToAddress", ""),
                "usdt":      int(t.get("quant") or t.get("amount") or t.get("value") or 0) / 1e6,
            })

        fetched = start + len(items)
        pct = min(fetched / max(total, 1), 1.0) * 0.4
        progress_bar.progress(pct)
        status_text.text(f"Fetching transfers… {fetched}/{total}")
        start += limit
        if fetched >= total or len(items) < limit or fetched >= MAX_TX:
            break
        time.sleep(DELAY)

    return txs

def fetch_tx_detail(tx_hash):
    try:
        data = get(f"{TRONSCAN_BASE}/transaction-info", {"hash": tx_hash})
        cost = data.get("cost") or {}
        energy_usage  = cost.get("energy_usage", 0)
        energy_fee    = cost.get("energy_fee", 0)
        energy_total  = cost.get("energy_usage_total", 0) or (energy_usage + int(energy_fee / ENERGY_UNIT_PRICE_SUN))
        net_fee       = cost.get("net_fee", 0)
        total_fee_sun = cost.get("fee", 0)
        trx_burned    = total_fee_sun / 1e6 if total_fee_sun else (energy_fee + net_fee) / 1e6
        trx_saved     = (energy_usage * ENERGY_UNIT_PRICE_SUN) / 1e6
        return {
            "energy_total":  energy_total,
            "energy_staked": energy_usage,
            "energy_burned": int(energy_fee / ENERGY_UNIT_PRICE_SUN) if ENERGY_UNIT_PRICE_SUN else 0,
            "trx_burned":    trx_burned,
            "trx_saved":     trx_saved,
        }
    except Exception:
        return {"energy_total":0,"energy_staked":0,"energy_burned":0,"trx_burned":0,"trx_saved":0}

def enrich(txs, progress_bar, status_text):
    total = len(txs)
    for i, tx in enumerate(txs, 1):
        tx.update(fetch_tx_detail(tx["tx_hash"]))
        progress_bar.progress(0.4 + (i / total) * 0.6)
        status_text.text(f"Fetching energy & fee details… {i}/{total}")
        time.sleep(DELAY)
    return txs

# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="TRON USDT Screener", page_icon="🔍", layout="wide")

st.title("🔍 USDT TRC-20 Wallet Screener")
st.caption("Scan outgoing USDT transfers · Energy consumed · TRX burned vs saved")

with st.sidebar:
    st.header("⚙️ Settings")
    wallet  = st.text_input("Wallet Address", placeholder="T...")
    days    = st.slider("Lookback period (days)", 7, 90, 30)
    run_btn = st.button("🚀 Scan Wallet", use_container_width=True)

if run_btn:
    if not wallet or not wallet.startswith("T") or len(wallet) < 30:
        st.error("Please enter a valid TRON wallet address.")
    else:
        now       = datetime.now(timezone.utc)
        from_date = now - timedelta(days=days)
        ts_start  = int(from_date.timestamp() * 1000)
        ts_end    = int(now.timestamp() * 1000)

        progress = st.progress(0.0)
        status   = st.empty()

        try:
            txs = fetch_outgoing(wallet, ts_start, ts_end, progress, status)

            if not txs:
                st.warning(f"No outgoing USDT transactions found in the last {days} days.")
            else:
                txs = enrich(txs, progress, status)
                progress.progress(1.0)
                status.text("✅ Done!")

                df = pd.DataFrame(txs)
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

                # ── Summary metrics ───────────────────────────────────────────
                total_usdt       = df["usdt"].sum()
                total_energy     = df["energy_total"].sum()
                energy_staked    = df["energy_staked"].sum()
                energy_burned    = df["energy_burned"].sum()
                total_trx_burned = df["trx_burned"].sum()
                total_trx_saved  = df["trx_saved"].sum()
                total_no_stake   = total_trx_burned + total_trx_saved
                savings_pct      = (total_trx_saved / total_no_stake * 100) if total_no_stake > 0 else 0

                st.subheader("📊 Summary")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Transactions",     len(df))
                c2.metric("USDT Sent",        f"{total_usdt:,.2f}")
                c3.metric("TRX Burned",       f"{total_trx_burned:.4f}")
                c4.metric("TRX Saved",        f"{total_trx_saved:.4f}", f"{savings_pct:.1f}% discount")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("Total Energy",     f"{int(total_energy):,}")
                c6.metric("Energy from Stake",f"{int(energy_staked):,}")
                c7.metric("Energy Burned",    f"{int(energy_burned):,}")
                c8.metric("Cost w/o Stake",   f"{total_no_stake:.4f} TRX")

                # ── Charts ────────────────────────────────────────────────────
                st.subheader("📈 Charts")
                ch1, ch2 = st.columns(2)

                with ch1:
                    st.caption("TRX Burned per Transaction")
                    chart_df = df.set_index("datetime")[["trx_burned"]].sort_index()
                    st.bar_chart(chart_df)

                with ch2:
                    st.caption("Energy Consumed per Transaction")
                    chart_df2 = df.set_index("datetime")[["energy_total"]].sort_index()
                    st.bar_chart(chart_df2)

                # ── Transaction table ─────────────────────────────────────────
                st.subheader("📋 Transactions")
                display = df[[
                    "datetime","usdt","energy_total","energy_staked",
                    "energy_burned","trx_burned","trx_saved","to_addr","tx_hash"
                ]].sort_values("datetime", ascending=False).copy()
                display.columns = [
                    "Date (UTC)","USDT","Energy Total","Energy Staked",
                    "Energy Burned","TRX Burned","TRX Saved","To Address","TX Hash"
                ]
                st.dataframe(display, use_container_width=True)

                # ── Export ────────────────────────────────────────────────────
                csv = display.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download CSV", csv,
                    file_name=f"usdt_outgoing_{wallet[:10]}.csv", mime="text/csv")

        except Exception as e:
            st.error(f"❌ Error: {e}")
