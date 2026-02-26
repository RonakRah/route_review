from __future__ import annotations

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(page_title="CSV Review → Google Sheet", layout="wide")
st.title("CSV Review → Google Sheet")

st.write(
    "Upload a CSV with columns **departure_pos**, **arrival_pos**, **Status**.\n\n"
    "Click **Accept** or **Reject** for each row. The **Final status** column updates immediately. "
    "When finished, click **Confirm done** to overwrite the Google Sheet tab with accepted rows."
)

# ----------------------------
# Google Sheets config (from .streamlit/secrets.toml)
# ----------------------------
SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
SHEET_NAME = st.secrets.get("SHEET_NAME", "accepted")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_gspread_client() -> gspread.Client:
    creds_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)

def overwrite_worksheet(worksheet: gspread.Worksheet, df_to_write: pd.DataFrame) -> None:
    worksheet.clear()
    values = [list(df_to_write.columns)]
    if not df_to_write.empty:
        values += df_to_write.astype(str).values.tolist()
    worksheet.update(values)

# ----------------------------
# Session state
# ----------------------------
if "df" not in st.session_state:
    st.session_state.df = None
if "file_signature" not in st.session_state:
    st.session_state.file_signature = None

# ----------------------------
# Upload CSV
# ----------------------------
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

REQUIRED_COLS = {"departure_pos", "arrival_pos", "Status"}

def load_df(file) -> pd.DataFrame:
    d = pd.read_csv(file)

    missing = REQUIRED_COLS - set(d.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    d.insert(0, "row_id", range(1, len(d) + 1))
    d["decision"] = "pending"  # pending/accepted/rejected
    return d

if uploaded_file is not None:
    signature = (uploaded_file.name, uploaded_file.size)
    if st.session_state.file_signature != signature:
        try:
            st.session_state.df = load_df(uploaded_file)
            st.session_state.file_signature = signature
            st.success("File loaded successfully.")
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
    # Small pill-like label
    if decision == "accepted":
        return '<span style="padding:4px 10px;border-radius:999px;background:#d1fae5;color:#065f46;font-weight:600;">accepted</span>'
    if decision == "rejected":
        return '<span style="padding:4px 10px;border-radius:999px;background:#fee2e2;color:#991b1b;font-weight:600;">rejected</span>'
    return '<span style="padding:4px 10px;border-radius:999px;background:#fef3c7;color:#92400e;font-weight:600;">pending</span>'

def big_id(x) -> str:
    return f'<span style="font-size:16px;font-weight:400;letter-spacing:0.2px;color:#1f2937;">{x}</span>'

# ----------------------------
# Table Header
# ----------------------------
# Columns: Row | Departure | Arrival | Status | Final status | Actions
# Styled header with background
header_style = """
<div style="
    background-color:#f3f4f6;
    padding:10px 8px;
    border-radius:8px;
    font-weight:600;
    margin-bottom:6px;
">
    <div style="display:grid;
                grid-template-columns:0.8fr 2.2fr 2.2fr 2fr 1.6fr 2.2fr;
                gap:8px;">
        <div>Row</div>
        <div>Departure</div>
        <div>Arrival</div>
        <div>Status</div>
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
    cols = st.columns([0.8, 2.2, 2.2, 2.0, 1.6, 2.2])

    cols[0].write(int(row["row_id"]))

    # Bigger font for IDs
    cols[1].markdown(big_id(row["departure_pos"]), unsafe_allow_html=True)
    cols[2].markdown(big_id(row["arrival_pos"]), unsafe_allow_html=True)

    cols[3].write(str(row["Status"]))

    # Final status column (no more status under the row)
    cols[4].markdown(decision_badge(row["decision"]), unsafe_allow_html=True)

    # Actions column with two buttons
    a1, a2 = cols[5].columns(2)
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
# Finish: overwrite Google Sheet tab with accepted rows
# ----------------------------
st.subheader("Finish → Write accepted rows to Google Sheet")

accepted_df = df[df["decision"] == "accepted"].copy()
export_df = accepted_df.drop(columns=["row_id", "decision"], errors="ignore")

st.write(f"Accepted rows: **{len(export_df)}**")

if st.button("✅ Confirm done"):
    if export_df.empty:
        st.warning("No accepted rows to write.")
        st.stop()

    try:
        client = get_gspread_client()
        sh = client.open_by_key(SPREADSHEET_ID)

        try:
            ws = sh.worksheet(SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(
                title=SHEET_NAME,
                rows=max(1000, len(export_df) + 5),
                cols=max(3, export_df.shape[1]),
            )

        overwrite_worksheet(ws, export_df)

        st.success("Google Sheet updated successfully.")
        st.info("You can close this page now.")
    except Exception as e:
        st.error(
            "Failed to write to Google Sheets.\n\n"
            f"Error: {e}"
        )