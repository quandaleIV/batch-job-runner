import boto3
import requests
import json
import os
from datetime import datetime

OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']
OUTPUT_PREFIX = os.environ.get('OUTPUT_PREFIX', 'output/')

s3 = boto3.client('s3', region_name='ap-southeast-2')

def fetch_asx_data():
    # Using Yahoo Finance API for ASX data - free, no API key needed
    symbols = ['BHP.AX', 'CBA.AX', 'ANZ.AX', 'WBC.AX', 'NAB.AX']
    results = []

    for symbol in symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            meta = data['chart']['result'][0]['meta']
            results.append({
                'symbol': symbol,
                'price': meta.get('regularMarketPrice'),
                'previous_close': meta.get('previousClose'),
                'currency': meta.get('currency'),
                'fetched_at': datetime.utcnow().isoformat()
            })
            print(f"Fetched {symbol}: ${meta.get('regularMarketPrice')}")

    return results

def save_to_s3(data):
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
    key = f"{OUTPUT_PREFIX}asx-data-{timestamp}.json"
    
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )
    print(f"Saved to s3://{OUTPUT_BUCKET}/{key}")

if __name__ == '__main__':
    print("Fetching ASX data...")
    data = fetch_asx_data()
    save_to_s3(data)
    print(f"Done. Fetched {len(data)} stocks.")