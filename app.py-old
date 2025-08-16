import os
import io
from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import plotly.graph_objs as go
import plotly
import json
import webbrowser
import threading

app = Flask(__name__)
app.secret_key = "change-me"

DEFAULT_COLMAP = {"desc": "Description", "amount": "Summary Amt."}

def parse_csv(file_storage):
    try:
        # Skip first 6 rows, use row 7 as header
        df = pd.read_csv(file_storage, engine="python", on_bad_lines='skip', skiprows=6)
        lines_skipped = False
    except TypeError:
        # For older pandas versions
        df = pd.read_csv(file_storage, engine="python", error_bad_lines=False, skiprows=6)
        lines_skipped = True
    # Drop 'Running Bal.' column if present
    if 'Running Bal.' in df.columns:
        df = df.drop(columns=['Running Bal.'])
    colmap = dict(desc='Description', amount='Amount')

    # Basic inference if needed
    def infer_col(name_parts):
        for c in df.columns:
            cl = c.lower()
            if any(p in cl for p in name_parts):
                return c
        return None

    colmap.setdefault('amount', infer_col(['amount','amt','value']))
    colmap.setdefault('date', infer_col(['date','posted','post date','transaction date']))
    colmap.setdefault('desc', infer_col(['description','details','memo','payee']))
    colmap.setdefault('category', infer_col(['category','cat']))
    colmap.setdefault('type', infer_col(['type','debit/credit','dr/cr']))

    # Amount column
    if colmap.get('amount'):
        df['_amount'] = pd.to_numeric(df[colmap['amount']].astype(str).str.replace(',', ''), errors='coerce')
    else:
        # Try split debit/credit
        lower_cols = [c.lower() for c in df.columns]
        amt = None
        if 'debit' in lower_cols:
            amt = -pd.to_numeric(df[df.columns[lower_cols.index('debit')]], errors='coerce')
        if 'credit' in lower_cols:
            credit = pd.to_numeric(df[df.columns[lower_cols.index('credit')]], errors='coerce')
            if amt is None: amt = credit
            else: amt = amt.fillna(0) + credit.fillna(0)
        df['_amount'] = amt

    # Dates
    if colmap.get('date'):
        df['_date'] = pd.to_datetime(df[colmap['date']], errors='coerce')
    else:
        df['_date'] = pd.NaT

    # Category
    if colmap.get('category'):
        df['_category'] = df[colmap['category']].astype(str)
    else:
        desc_col = colmap.get('desc') or df.columns[0]
        def guess_cat(s: str) -> str:
            s = str(s).lower()
            if any(k in s for k in ['uber','lyft','gas','shell','chevron','exxon']):
                return 'Transport'
            if any(k in s for k in ['amazon','walmart','target','costco','grocery','market']):
                return 'Shopping/Groceries'
            if any(k in s for k in ['starbucks','coffee','restaurant','pizza','burger','cafe']):
                return 'Food & Drink'
            if any(k in s for k in ['rent','mortgage','landlord','hoa','property']):
                return 'Housing'
            if any(k in s for k in ['salary','payroll','deposit','ach credit','refund']):
                return 'Income'
            if any(k in s for k in ['insurance','geico','allstate','state farm']):
                return 'Insurance'
            if any(k in s for k in ['electric','water','utility','internet','comcast','xfinity','verizon','t-mobile','at&t']):
                return 'Utilities'
            return 'Other'
        df['_category'] = df[desc_col].astype(str).map(guess_cat)

    # Sign fix using type when all positive
    if colmap.get('type') and df['_amount'] is not None and df['_amount'].ge(0).all():
        tcol = df[colmap['type']].astype(str).str.lower()
        df.loc[tcol.str.contains('debit|withdraw|payment', na=False), '_amount'] *= -1

    # Drop NaN amounts
    if '_amount' in df.columns:
        df = df[pd.notna(df['_amount'])]

    return df, colmap

def group_by_first_two_words(df: pd.DataFrame, desc_col: str, amount_col: str):
    # Extract first two words from description
    def first_two_words(s):
        return ' '.join(str(s).split()[:2])
    df['desc_group'] = df[desc_col].map(first_two_words)
    grouped = df.groupby('desc_group')[amount_col].sum().reset_index()
    grouped = grouped.sort_values(amount_col, ascending=False)
    return grouped

def build_charts(df: pd.DataFrame):
    total_in = float(df.loc[df['_amount']>0, '_amount'].sum()) if '_amount' in df.columns else 0.0
    total_out = float(-df.loc[df['_amount']<0, '_amount'].sum()) if '_amount' in df.columns else 0.0
    net = float(df['_amount'].sum()) if '_amount' in df.columns else 0.0

    kpis = {"total_in": total_in, "total_out": total_out, "net": net}

    # Monthly trend
    if '_date' in df.columns and df['_date'].notna().any():
        monthly = df.groupby(df['_date'].dt.to_period('M'))['_amount'].sum().to_timestamp()
        trend = go.Figure()
        trend.add_trace(go.Bar(x=monthly.index.astype(str), y=monthly.values, name='Net'))
        trend.update_layout(margin=dict(l=20,r=20,t=30,b=20), height=300)
        trend_json = json.dumps(trend, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        trend_json = None

    # Top spend categories
    if '_amount' in df.columns:
        spend = df.loc[df['_amount']<0].groupby('_category')['_amount'].sum().sort_values().abs().head(10)
    else:
        spend = pd.Series(dtype=float)
    pie = go.Figure(data=[go.Pie(labels=list(spend.index), values=list(spend.values))])
    pie.update_layout(margin=dict(l=20,r=20,t=30,b=20), height=300)
    pie_json = json.dumps(pie, cls=plotly.utils.PlotlyJSONEncoder)

    # Latest transactions
    latest = df.copy()
    if '_date' in df.columns and df['_date'].notna().any():
        latest = latest.sort_values('_date', ascending=False)
    latest = latest.head(10)

    return kpis, trend_json, pie_json, latest


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files or request.files['file'].filename == '':
        flash('Please choose a CSV file first.')
        return redirect(url_for('index'))
    file = request.files['file']
    try:
        df, colmap = parse_csv(file)
        if df.empty:
            flash('No valid rows were found in that CSV.')
            return redirect(url_for('index'))

        kpis, trend_json, pie_json, latest = build_charts(df)

        # Choose up to 3 original columns to show
        base_cols = [c for c in df.columns if not c.startswith('_')]
        show_cols = base_cols[:3]

        # Build table columns (include derived ones if useful)
        table_cols = []
        if '_date' in df.columns: table_cols.append('_date')
        if '_amount' in df.columns: table_cols.append('_amount')
        if '_category' in df.columns: table_cols.append('_category')
        table_cols += show_cols
        # Drop duplicates while preserving order
        seen = set()
        table_cols = [c for c in table_cols if not (c in seen or seen.add(c))]

        latest_view = latest[table_cols]

        # Humanize column names
        display_cols = [c.replace('_',' ').title() for c in table_cols]
        table_records = latest_view.to_dict(orient='records')

        # Description summary data
        desc_col = colmap.get('desc') or 'Description'
        amount_col = colmap.get('amount') or 'Amount'
        desc_summary = group_by_first_two_words(df, desc_col, '_amount')
        desc_summary_records = desc_summary.to_dict(orient='records')

        # Transactions from the most recent date
        if '_date' in df.columns and df['_date'].notna().any():
            most_recent_date = df['_date'].max()
            recent_df = df[df['_date'] == most_recent_date]
            recent_view = recent_df[table_cols] if not recent_df.empty else recent_df
            recent_records = recent_view.to_dict(orient='records')
        else:
            recent_records = []

        return render_template('dashboard.html',
                       kpis=kpis,
                       trend_json=trend_json,
                       pie_json=pie_json,
                       table=table_records,
                       columns=display_cols,
                       desc_summary=desc_summary_records,
                       recent_transactions=recent_records)
    except Exception as e:
        flash(f'Failed to analyze CSV: {e}')
        return redirect(url_for('index'))

if __name__ == "__main__":
    def open_browser_once():
        if not os.environ.get("BROWSER_OPENED"):
            webbrowser.open_new("http://127.0.0.1:5000/")
            os.environ["BROWSER_OPENED"] = "1"
    threading.Timer(1.5, open_browser_once).start()
    app.run(debug=True, use_reloader=False)