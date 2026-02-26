from __future__ import annotations

import streamlit as st
import pandas as pd

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(page_title="Route Review", layout="wide")
st.title("Route Review")

st.write(
    "Upload a CSV with columns **departure_pos**, **arrival_pos**, **from_name**, **to_name**.\n\n"
    "Click **Accept** or **Reject** per row. The **Final status** updates immediately.\n"
    "When finished, download the accepted rows as CSV."
)

# ----------------------------
# Session state
# ----------------------------
if "df" not in st.session_state:
    st.session_state.df = None
if "file_signature" not in st.session_state:
    st.session_state.file_signature = None
if "filename" not in st.session_state:
    st.session_state.filename = "data.csv"

# ----------------------------
# Upload CSV
# ----------------------------
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

REQUIRED_COLS = {"departure_pos", "arrival_pos", "from_name", "to_name"}

def load_df(file) -> pd.DataFrame:
    d = pd.read_csv(file)

    missing = REQUIRED_COLS - set(d.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    # stable id + decision column
    d.insert(0, "row_id", range(1, len(d) + 1))
    d["decision"] = "pending"  # pending/accepted/rejected
    return d

if uploaded_file is not None:
    signature = (uploaded_file.name, uploaded_file.size)
    if st.session_state.file_signature != signature:
        try:
            st.session_state.df = load_df(uploaded_file)
            st.session_state.file_signature = signature
            st.session_state.filename = uploaded_file.name
            st.success(f"Loaded: {uploaded_file.name}")
        except Exception as e:
            st.session_state.df = None
            st.error(str(e))

if st.session_state.df is None:
    st.info("Upload a CSV to start.")
    st.stop()

df = st.session_state.df

# ----------------------------
# Stats
# ----------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", len(df))
col2.metric("Pending", int((df["decision"] == "pending").sum()))
col3.metric("Accepted", int((df["decision"] == "accepted").sum()))
col4.metric("Rejected", int((df["decision"] == "rejected").sum()))

st.divider()

# ----------------------------
# Helpers for styling
# ----------------------------
def decision_badge(decision: str) -> str:
    if decision == "accepted":
        return '<span style="padding:4px 10px;border-radius:999px;background:#d1fae5;color:#065f46;font-weight:600;">accepted</span>'
    if decision == "rejected":
        return '<span style="padding:4px 10px;border-radius:999px;background:#fee2e2;color:#991b1b;font-weight:600;">rejected</span>'
    return '<span style="padding:4px 10px;border-radius:999px;background:#fef3c7;color:#92400e;font-weight:600;">pending</span>'

def big_id(x) -> str:
    # slightly bigger + dark blue, not bold
    return f'<span style="font-size:16px;font-weight:500;color:#1e3a8a;">{x}</span>'

# ----------------------------
# Styled header with background
# ----------------------------
header_style = """
<div style="
    background-color:#e5e7eb;
    color:#111827;
    padding:10px 8px;
    border-radius:8px;
    font-weight:600;
    margin-bottom:6px;
">
    <div style="display:grid;
                grid-template-columns:0.8fr 1.8fr 1.8fr 2fr 2fr 1.6fr 2.2fr;
                gap:8px;">
        <div>Row</div>
        <div>Departure</div>
        <div>Arrival</div>
        <div>From</div>
        <div>To</div>
        <div>Final status</div>
        <div>Actions</div>
    </div>
</div>
"""
st.markdown(header_style, unsafe_allow_html=True)

# ----------------------------
# Table Rows
# ----------------------------
for i, row in df.iterrows():
    cols = st.columns([0.8, 1.8, 1.8, 2.0, 2.0, 1.6, 2.2])

    cols[0].write(int(row["row_id"]))
    cols[1].markdown(big_id(row["departure_pos"]), unsafe_allow_html=True)
    cols[2].markdown(big_id(row["arrival_pos"]), unsafe_allow_html=True)
    cols[3].write(str(row["from_name"]))
    cols[4].write(str(row["to_name"]))
    cols[5].markdown(decision_badge(row["decision"]), unsafe_allow_html=True)

    a1, a2 = cols[6].columns(2)
    if a1.button("✅ Accept", key=f"accept_{row['row_id']}"):
        df.at[i, "decision"] = "accepted"
        st.session_state.df = df
        st.rerun()

    if a2.button("❌ Reject", key=f"reject_{row['row_id']}"):
        df.at[i, "decision"] = "rejected"
        st.session_state.df = df
        st.rerun()

st.divider()

# ----------------------------
# Download accepted rows
# ----------------------------
st.subheader("Finish → Download accepted rows as CSV")

accepted_df = df[df["decision"] == "accepted"].copy()
export_df = accepted_df.drop(columns=["row_id", "decision"], errors="ignore")

st.write(f"Accepted rows: **{len(export_df)}**")

if export_df.empty:
    st.info("No accepted rows yet.")
else:
    base_name = st.session_state.filename.rsplit(".", 1)[0]
    out_name = f"{base_name}-accepted.csv"
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇ Download accepted CSV",
        data=csv_bytes,
        file_name=out_name,
        mime="text/csv",
    )