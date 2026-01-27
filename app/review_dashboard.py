import streamlit as st
from RIVO.db.db_handler import fetch_pending_reviews, mark_review_decision

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
        value=row["draft_email"],
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
