import streamlit as st
from pathlib import Path
import sys

# Ensure project root is importable when running `streamlit run app/review_dashboard.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
project_root_str = str(PROJECT_ROOT)
if SCRIPT_DIR in sys.path:
    sys.path.remove(SCRIPT_DIR)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

from db.db_handler import fetch_pending_reviews, mark_review_decision

st.set_page_config(page_title="Revo – Human Review Panel", layout="wide")

st.title("🧠 Revo – Human-in-the-Loop Review")

# Fetch BOTH Pending + Structural Failed
pending = fetch_pending_reviews(include_structural_failed=True)

if pending.empty:
    st.success("No pending reviews 🎉")
    st.stop()

for _, row in pending.iterrows():
    st.markdown("---")
    st.subheader(f"Lead: {row['name']} ({row['company']})")

    # Status badge
    if row["review_status"] == "STRUCTURAL_FAILED":
        st.error("❌ Structural Validation Failed")
    else:
        st.info("🟡 Pending Review")

    st.write("**Confidence Score:**", row.get("confidence_score", "N/A"))

    edited_email = st.text_area(
        "Draft Email",
        value=row["draft_message"],
        height=220,
        key=f"email_{row['id']}"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Approve", key=f"approve_{row['id']}"):
            mark_review_decision(row["id"], "Approved", edited_email)
            st.success("Approved and sent!")

    with col2:
        if st.button("❌ Reject", key=f"reject_{row['id']}"):
            mark_review_decision(row["id"], "Rejected", edited_email)
            st.warning("Rejected.")
