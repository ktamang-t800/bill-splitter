import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests

st.set_page_config(page_title="Bill Splitter", layout="wide")
st.title("Bill Splitter with Friends")

# Country to currency mapping
COUNTRY_CURRENCY = {
    "Vietnam": ("VND", "₫"),
    "United States": ("USD", "$"),
    "China": ("CNY", "¥"),
    "United Kingdom": ("GBP", "£"),
    "European Union": ("EUR", "€"),
    "Japan": ("JPY", "¥"),
    "Australia": ("AUD", "A$"),
    "Canada": ("CAD", "C$"),
    # Add more countries as needed
}

# Step 0: Country search and select
country_search = st.text_input("Type your country to search", value="Vietnam")

# Filter matching countries
filtered_countries = [c for c in COUNTRY_CURRENCY.keys() if country_search.lower() in c.lower()]

if not filtered_countries:
    st.warning("No country matches your search. Please try again.")
    selected_country = None
    currency_code = None
    currency_symbol = None
else:
    selected_country = st.selectbox("Select your country", filtered_countries)
    currency_code, currency_symbol = COUNTRY_CURRENCY[selected_country]
    st.write(f"Currency detected: {currency_code} {currency_symbol}")

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def create_pdf(participants, expenses_df, balances, payments, currency_symbol):
    safe_currency_symbol = currency_symbol
    if currency_symbol == "₫":
        safe_currency_symbol = "VND "

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Bill Splitter Report", ln=True, align="C")
    pdf.ln(10)

    # Participants
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Participants:", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, ", ".join(participants))
    pdf.ln(5)

    # Expenses
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Expenses:", ln=True)
    pdf.set_font("Arial", "", 10)
    col_widths = [60, 30, 40, 50]
    headers = ["Description", "Amount", "Payer", "Sharers"]
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1)
    pdf.ln()
    for _, row in expenses_df.iterrows():
        pdf.cell(col_widths[0], 10, str(row["Description"])[:30], border=1)
        pdf.cell(col_widths[1], 10, f"{safe_currency_symbol}{row['Amount']:.2f}", border=1, align="R")
        pdf.cell(col_widths[2], 10, row["Payer"], border=1)
        pdf.cell(col_widths[3], 10, row["Sharers"], border=1)
        pdf.ln()
    pdf.ln(5)

    # Balances
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Balances:", ln=True)
    pdf.set_font("Arial", "", 12)
    for person, balance in balances.items():
        if balance > 0:
            pdf.cell(0, 10, f"{person} is owed {safe_currency_symbol}{balance:.2f}", ln=True)
        elif balance < 0:
            pdf.cell(0, 10, f"{person} owes {safe_currency_symbol}{-balance:.2f}", ln=True)
        else:
            pdf.cell(0, 10, f"{person} is settled up.", ln=True)
    pdf.ln(5)

    # Payment Recommendations
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Payment Recommendations:", ln=True)
    pdf.set_font("Arial", "", 12)
    if payments:
        for debtor, creditor, amount in payments:
            pdf.cell(0, 10, f"{debtor} pays {creditor} {safe_currency_symbol}{amount:.2f}", ln=True)
    else:
        pdf.cell(0, 10, "All balances are settled!", ln=True)

    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

# Participants
if "participants" not in st.session_state:
    st.session_state.participants = []

with st.expander("Step 1: Enter Group Participants", expanded=True):
    with st.form("participants_form", clear_on_submit=True):
        new_participant = st.text_input("Add participant name", key="participant_input")
        submitted = st.form_submit_button("Add participant")
        if submitted:
            name = new_participant.strip()
            if not name:
                st.error("Participant name cannot be empty.")
            elif name in st.session_state.participants:
                st.warning("Participant already added.")
            else:
                st.session_state.participants.append(name)
                st.success(f"Added participant: {name}")

    if st.session_state.participants:
        st.write("Current participants:")
        st.write(", ".join(st.session_state.participants))
    else:
        st.info("Add participants to start")

st.markdown("---")

# Expenses
if st.session_state.participants:
    with st.expander("Step 2: Add Expenses", expanded=True):
        if "expenses" not in st.session_state:
            st.session_state.expenses = []

        with st.form("expense_form", clear_on_submit=True):
            col1, col2, col3 = st.columns([4, 2, 3])
            with col1:
                description = st.text_input("Expense description", key="desc_input")
            with col2:
                amount = st.number_input("Amount", min_value=0.0, format="%.2f", key="amount_input")
            with col3:
                payer = st.selectbox("Paid by", st.session_state.participants, key="payer_input")
            sharers = st.multiselect(
                "Split among (select participants who share this expense)",
                st.session_state.participants,
                default=st.session_state.participants,
                key="sharers_input"
            )
            add_expense = st.form_submit_button("Add Expense")

        if add_expense:
            if not description.strip():
                st.error("Please enter an expense description.")
            elif amount <= 0:
                st.error("Amount must be greater than zero.")
            elif not payer:
                st.error("Please select the payer.")
            elif not sharers:
                st.error("Please select at least one sharer.")
            elif payer not in st.session_state.participants:
                st.error("Payer must be in participants list.")
            else:
                st.session_state.expenses.append({
                    "Description": description.strip(),
                    "Amount": amount,
                    "Payer": payer,
                    "Sharers": sharers
                })
                st.success(f"Added expense: {description.strip()} - {currency_symbol}{amount:.2f}")

    if st.session_state.expenses:
        df_expenses = pd.DataFrame([
            {
                "Description": e["Description"],
                "Amount": e["Amount"],
                "Payer": e["Payer"],
                "Sharers": ", ".join(e["Sharers"])
            }
            for e in st.session_state.expenses
        ])
        st.subheader("Expenses List")

        # Add delete button for each row
        for i, row in df_expenses.iterrows():
            cols = st.columns([4, 2, 2, 3, 1])
            cols[0].write(row["Description"])
            cols[1].write(f"{currency_symbol}{row['Amount']:.2f}")
            cols[2].write(row["Payer"])
            cols[3].write(row["Sharers"])
            # Delete button
            if cols[4].button("Delete", key=f"delete_{i}"):
                st.session_state.expenses.pop(i)
                st.rerun()
                break  # Needed so index does not go out of range after rerun

        balances = {p: 0 for p in st.session_state.participants}
        for e in st.session_state.expenses:
            amount_per_person = e["Amount"] / len(e["Sharers"])
            for sharer in e["Sharers"]:
                balances[sharer] -= amount_per_person
            balances[e["Payer"]] += e["Amount"]

        balances_df = pd.DataFrame(
            [(person, balance) for person, balance in balances.items()],
            columns=["Participant", "Balance"]
        )
        st.subheader("Balances")
        for person, balance in balances.items():
            color = "green" if balance > 0 else ("red" if balance < 0 else "black")
            if balance > 0:
                st.markdown(f"<span style='color:{color}'>{person} is owed {currency_symbol}{balance:.2f}</span>", unsafe_allow_html=True)
            elif balance < 0:
                st.markdown(f"<span style='color:{color}'>{person} owes {currency_symbol}{-balance:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:{color}'>{person} is settled up.</span>", unsafe_allow_html=True)

        def calculate_payments(balances):
            creditors = {p: b for p, b in balances.items() if b > 0}
            debtors = {p: -b for p, b in balances.items() if b < 0}

            payments = []

            creditor_iter = iter(creditors.items())
            debtor_iter = iter(debtors.items())

            try:
                creditor, creditor_amt = next(creditor_iter)
                debtor, debtor_amt = next(debtor_iter)

                while True:
                    pay_amt = min(creditor_amt, debtor_amt)
                    payments.append((debtor, creditor, pay_amt))

                    creditor_amt -= pay_amt
                    debtor_amt -= pay_amt

                    if creditor_amt == 0:
                        creditor, creditor_amt = next(creditor_iter)
                    if debtor_amt == 0:
                        debtor, debtor_amt = next(debtor_iter)

            except StopIteration:
                pass

            return payments

        payments = calculate_payments(balances)

        st.subheader("Payment Recommendations")
        if payments:
            for debtor, creditor, amount in payments:
                st.write(f"{debtor} pays {creditor} {currency_symbol}{amount:.2f}")
        else:
            st.info("All balances are settled!")

        pdf_bytes = create_pdf(st.session_state.participants, df_expenses, balances, payments, currency_symbol)

        st.download_button(
            label="Download Full Report as PDF",
            data=pdf_bytes,
            file_name="bill_splitter_report.pdf",
            mime="application/pdf"
        )
