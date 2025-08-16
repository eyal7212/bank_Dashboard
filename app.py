import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
from io import StringIO

st.set_page_config(page_title="Bank Statement Analyzer", layout="wide")
st.title("🏦 Bank Statement Analyzer")

uploaded_file = st.file_uploader("Upload a bank statement (.csv)", type=["csv"])

if uploaded_file:
    # Read and clean raw lines
    lines = uploaded_file.getvalue().decode("utf-8").splitlines()[6:]
    pattern = re.compile(r'(?P<date>\d{2}/\d{2}/\d{4}),"(.*?)","(-?\d+\.\d+)",("?-?\d+\.\d+)"?')

    records = []
    for line in lines[1:]:
        match = pattern.search(line)
        if match:
            date, desc, amt, bal = match.groups()
            amt = amt.replace('"', '').strip()
            bal = bal.replace('"', '').strip()
            records.append((date, desc, float(amt), float(bal)))

    # Build DataFrame
    df = pd.DataFrame(records, columns=["Date", "Description", "Amount", "Running Balance"])
    df["Date"] = pd.to_datetime(df["Date"])

    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    start = st.sidebar.date_input("Start Date", df["Date"].min().date())
    end = st.sidebar.date_input("End Date", df["Date"].max().date())
    keyword = st.sidebar.text_input("Search Description").lower()

    # Apply filters
    filtered = df[
        (df["Date"].dt.date >= start) &
        (df["Date"].dt.date <= end) &
        (df["Description"].str.lower().str.contains(keyword))
    ]

    st.write("### 📄 Filtered Transactions", filtered)

    # KPIs
    income = filtered[filtered["Amount"] > 0]["Amount"].sum()
    expense = filtered[filtered["Amount"] < 0]["Amount"].sum()
    balance = filtered["Running Balance"].iloc[-1] if not filtered.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Income", f"${income:,.2f}")
    col2.metric("💸 Total Expenses", f"${expense:,.2f}")
    col3.metric("📊 Ending Balance", f"${balance:,.2f}")

    # Charts
    st.write("### 📈 Balance Over Time")
    fig1, ax1 = plt.subplots()
    ax1.plot(filtered["Date"], filtered["Running Balance"])
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Running Balance")
    st.pyplot(fig1)

    st.write("### 🧾 Monthly Income vs Expenses")
    monthly = filtered.copy()
    monthly["Month"] = monthly["Date"].dt.to_period("M")
    summary = monthly.groupby("Month")["Amount"].agg([
        ("Income", lambda x: x[x > 0].sum()),
        ("Expenses", lambda x: x[x < 0].sum())
    ]).reset_index()
    summary["Month"] = summary["Month"].astype(str)

    fig2, ax2 = plt.subplots()
    ax2.bar(summary["Month"], summary["Income"], label="Income")
    ax2.bar(summary["Month"], summary["Expenses"], label="Expenses")
    ax2.legend()
    plt.xticks(rotation=45)
    st.pyplot(fig2)
