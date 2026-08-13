import os
import json
import sqlite3
import time
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")
DB_PATH = "my-list/cache.db"

def init_db():
    os.makedirs("my-list", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 기업 고유번호 매핑 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS corp_codes (
                    corp_code TEXT PRIMARY KEY,
                    corp_name TEXT,
                    stock_code TEXT,
                    modify_date TEXT
                 )''')
    # 원천 데이터 캐싱 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS api_cache (
                    endpoint TEXT,
                    params TEXT,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (endpoint, params)
                 )''')
    conn.commit()
    conn.close()

def get_corp_codes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 상장사만 가져오기 (stock_code가 있는 경우)
    c.execute("SELECT corp_code, corp_name, stock_code FROM corp_codes WHERE stock_code IS NOT NULL AND stock_code != ' '")
    results = c.fetchall()
    conn.close()
    
    if not results:
        update_corp_codes()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT corp_code, corp_name, stock_code FROM corp_codes WHERE stock_code IS NOT NULL AND stock_code != ' '")
        results = c.fetchall()
        conn.close()
        
    return results

def update_corp_codes():
    if not DART_API_KEY:
        raise ValueError("DART_API_KEY가 .env 파일에 설정되지 않았습니다.")
        
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {'crtfc_key': DART_API_KEY}
    res = requests.get(url, params=params)
    
    if res.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            xml_data = z.read('CORPCODE.xml')
            
        root = ET.fromstring(xml_data)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for item in root.findall('list'):
            corp_code = item.find('corp_code').text
            corp_name = item.find('corp_name').text
            stock_code = item.find('stock_code').text
            modify_date = item.find('modify_date').text
            
            c.execute('''INSERT OR REPLACE INTO corp_codes 
                         (corp_code, corp_name, stock_code, modify_date) 
                         VALUES (?, ?, ?, ?)''', (corp_code, corp_name, stock_code, modify_date))
        conn.commit()
        conn.close()

def fetch_dart_api(endpoint, params):
    # 캐시 확인
    params_copy = params.copy()
    if 'crtfc_key' in params_copy:
        del params_copy['crtfc_key'] # API 키는 캐시 키에서 제외
    params_str = json.dumps(params_copy, sort_keys=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT response FROM api_cache WHERE endpoint=? AND params=?", (endpoint, params_str))
    row = c.fetchone()
    
    if row:
        conn.close()
        return json.loads(row[0])
        
    # Queue/Rate Limit 우회를 위한 최소 슬립
    time.sleep(0.3)
    
    base_url = "https://opendart.fss.or.kr/api"
    full_url = f"{base_url}{endpoint}"
    
    actual_params = params.copy()
    actual_params['crtfc_key'] = DART_API_KEY
    res = requests.get(full_url, params=actual_params)
    
    if res.status_code == 200:
        data = res.json()
        # 000: 성공, 013: 데이터 없음
        if data.get('status') == '000' or data.get('status') == '013': 
            c.execute("INSERT OR REPLACE INTO api_cache (endpoint, params, response) VALUES (?, ?, ?)", 
                      (endpoint, params_str, json.dumps(data)))
            conn.commit()
        conn.close()
        return data
    else:
        conn.close()
        return None

def get_historical_prices(stock_code, years=10):
    endpoint = "fdr_prices"
    params_str = f"{stock_code}_{years}y_weekly"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT response FROM api_cache WHERE endpoint=? AND params=?", (endpoint, params_str))
    row = c.fetchone()
    
    if row:
        conn.close()
        return json.loads(row[0])
        
    # Calculate start date (10 years ago from today)
    end_date = datetime.today()
    start_date = end_date.replace(year=end_date.year - years)
    
    try:
        # Fetch daily prices
        df = fdr.DataReader(stock_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        if df.empty:
            conn.close()
            return []
            
        # 매주 금요일(주말일) 종가 기준으로 리샘플링
        df_weekly = df.resample('W-FRI').last()
        df_weekly = df_weekly.dropna(subset=['Close'])
        
        # Convert to list of dicts
        prices = []
        for index, row_data in df_weekly.iterrows():
            prices.append({
                'date': index.strftime('%Y-%m-%d'),
                'price': float(row_data['Close'])
            })
            
        c.execute("INSERT OR REPLACE INTO api_cache (endpoint, params, response) VALUES (?, ?, ?)", 
                  (endpoint, params_str, json.dumps(prices)))
        conn.commit()
        conn.close()
        return prices
    except Exception as e:
        print(f"Error fetching historical prices for {stock_code}: {e}")
        conn.close()
        return []

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def search_corp(query):
    codes = get_corp_codes()
    best_match = None
    best_dist = float('inf')
    
    for code, name, stock_code in codes:
        # 완전히 동일한 경우 즉시 반환
        if query == name or query == stock_code:
            return {"corp_code": code, "corp_name": name, "stock_code": stock_code}
            
        dist = levenshtein_distance(query, name)
        # 오타 허용 범위 (거리 2 이하)
        if dist < best_dist and dist <= 2: 
            best_dist = dist
            best_match = {"corp_code": code, "corp_name": name, "stock_code": stock_code}
            
    return best_match

init_db()
