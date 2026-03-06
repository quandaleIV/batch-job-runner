import boto3
import requests
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from fpdf import FPDF
from datetime import datetime, timedelta
from io import BytesIO

OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']
OUTPUT_PREFIX = os.environ.get('OUTPUT_PREFIX', 'output/')
FOREX_PAIR = os.environ.get('FOREX_PAIR', 'AUD/USD')
API_KEY = os.environ.get('TWELVE_DATA_API_KEY', 'demo')

s3 = boto3.client('s3', region_name='ap-southeast-2')

def fetch_forex_data():
    symbol = FOREX_PAIR.replace('/', '')
    url = f"https://api.twelvedata.com/time_series"
    params = {
        'symbol': FOREX_PAIR,
        'interval': '1day',
        'outputsize': 30,
        'apikey': API_KEY
    }
    response = requests.get(url, params=params)
    data = response.json()

    if 'values' not in data:
        print(f"API response: {data}")
        raise Exception("Failed to fetch forex data")

    values = data['values']
    df = pd.DataFrame(values)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df = df.sort_values('datetime')
    return df

def calculate_indicators(df):
    df['ma7'] = df['close'].rolling(window=7).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def generate_chart(df):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle(f'{FOREX_PAIR} — 30 Day Analysis', fontsize=14, fontweight='bold')

    ax1.plot(df['datetime'], df['close'], label='Close', linewidth=2, color='#2E6DA4')
    ax1.plot(df['datetime'], df['ma7'], label='MA7', linewidth=1.5, color='#E8A838', linestyle='--')
    ax1.plot(df['datetime'], df['ma20'], label='MA20', linewidth=1.5, color='#E84038', linestyle='--')
    ax1.set_ylabel('Price')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))

    ax2.plot(df['datetime'], df['rsi'], label='RSI(14)', linewidth=2, color='#6A0DAD')
    ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='Overbought (70)')
    ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='Oversold (30)')
    ax2.set_ylabel('RSI')
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

def generate_pdf(df, chart_buf):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 15, f'{FOREX_PAIR} Analysis Report', ln=True, align='C')
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}', ln=True, align='C')
    pdf.ln(5)

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = latest['close'] - prev['close']
    change_pct = (change / prev['close']) * 100

    pdf.set_font('Helvetica', 'B', 13)
    pdf.cell(0, 10, 'Summary', ln=True)
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, f"Latest Close: {latest['close']:.5f}", ln=True)
    pdf.cell(0, 8, f"Daily Change: {change:+.5f} ({change_pct:+.2f}%)", ln=True)
    pdf.cell(0, 8, f"MA7: {latest['ma7']:.5f}", ln=True)
    pdf.cell(0, 8, f"MA20: {latest['ma20']:.5f}", ln=True)
    pdf.cell(0, 8, f"RSI(14): {latest['rsi']:.1f}", ln=True)
    pdf.ln(5)

    chart_buf.seek(0)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp.write(chart_buf.read())
        tmp_path = tmp.name
    pdf.image(tmp_path, x=10, w=190)

    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return output

def save_to_s3(pdf_buf):
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
    pair_clean = FOREX_PAIR.replace('/', '')
    key = f"{OUTPUT_PREFIX}{pair_clean}-report-{timestamp}.pdf"
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=key,
        Body=pdf_buf.read(),
        ContentType='application/pdf'
    )
    print(f"Saved report to s3://{OUTPUT_BUCKET}/{key}")
    return key

if __name__ == '__main__':
    print(f"Generating {FOREX_PAIR} report...")
    df = fetch_forex_data()
    df = calculate_indicators(df)
    chart_buf = generate_chart(df)
    pdf_buf = generate_pdf(df, chart_buf)
    save_to_s3(pdf_buf)
    print("Done.")