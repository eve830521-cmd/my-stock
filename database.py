import os
import re
import json
import sqlite3
import time
import threading
import requests
from requests.adapters import HTTPAdapter
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

_db_lock = threading.Lock()
_rate_lock = threading.Lock()
_last_api_call_ts = 0.0
_MIN_API_INTERVAL = 0.08  # 초당 최대 ~12회 (OpenDART 분당 1000회 제한 안전권)

_http_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
_http_session.mount("https://", _adapter)
_http_session.mount("http://", _adapter)

# 메모리 캐시 (기업코드 목록)
_corp_codes_cache = None

# 한영 브랜드명 별칭 매핑 (양방향 정규화용)
KOR_TO_ENG_ALIASES = [
    ("나이스", "NICE"),
    ("네이버", "NAVER"),
    ("엘지", "LG"),
    ("에스케이", "SK"),
    ("케이티", "KT"),
    ("포스코", "POSCO"),
    ("씨제이", "CJ"),
    ("제이더블유", "JW"),
    ("지에스", "GS"),
    ("엘에스", "LS"),
    ("에이치디", "HD"),
    ("디엘", "DL"),
    ("오씨아이", "OCI"),
    ("케이씨씨", "KCC"),
    ("케이비", "KB"),
    ("엔에이치", "NH"),
    ("비엔케이", "BNK"),
    ("디지비", "DGB"),
    ("제이비", "JB"),
    ("에이치엘", "HL"),
    ("엘앤에프", "엘앤에프"),
    ("제이콘텐트리", "콘텐트리중앙"),
]


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    return conn


def init_db():
    os.makedirs("my-list", exist_ok=True)
    with _db_lock:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
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
    global _corp_codes_cache
    if _corp_codes_cache is not None and len(_corp_codes_cache) > 0:
        return _corp_codes_cache

    conn = _get_conn()
    c = conn.cursor()
    # 상장사만 가져오기 (modify_date 내림차순으로 정렬하여 합병/폐지된 동명이인 구법인보다 현존 상장법인이 우선 매칭되도록 보장)
    c.execute("""
        SELECT corp_code, corp_name, TRIM(stock_code) as sc, modify_date
        FROM corp_codes
        WHERE stock_code IS NOT NULL AND TRIM(stock_code) != ''
        ORDER BY modify_date DESC
    """)
    results = c.fetchall()
    conn.close()

    if not results:
        update_corp_codes()
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT corp_code, corp_name, TRIM(stock_code) as sc, modify_date
            FROM corp_codes
            WHERE stock_code IS NOT NULL AND TRIM(stock_code) != ''
            ORDER BY modify_date DESC
        """)
        results = c.fetchall()
        conn.close()

    # (corp_code, corp_name, stock_code) 형태로 반환하되 최신 modify_date 우선 유지
    _corp_codes_cache = [(r[0], r[1].strip() if r[1] else "", r[2].strip() if r[2] else "") for r in results]
    return _corp_codes_cache


def update_corp_codes():
    global _corp_codes_cache
    if not DART_API_KEY:
        raise ValueError("DART_API_KEY가 .env 파일에 설정되지 않았습니다.")

    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {'crtfc_key': DART_API_KEY}
    res = _http_session.get(url, params=params, timeout=20)

    if res.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(res.content)) as z:
            xml_data = z.read('CORPCODE.xml')

        root = ET.fromstring(xml_data)

        with _db_lock:
            conn = _get_conn()
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
        _corp_codes_cache = None


def check_cached_dart_api(endpoint, params):
    """네트워크 호출 없이 DB 캐시에 저장된 응답이 있는지 확인"""
    params_copy = params.copy()
    params_copy.pop('crtfc_key', None)
    params_str = json.dumps(params_copy, sort_keys=True)

    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT response, timestamp FROM api_cache WHERE endpoint=? AND params=?", (endpoint, params_str))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    data = json.loads(row[0])
    # 과거 연도(현재 연도 미만)의 013(데이터 없음) 캐시는 영구 유효
    # 당해 연도의 013 캐시는 당일(같은 날짜) 동안만 유효 처리하여 불필요한 반복 호출 방지
    if data.get('status') == '013':
        bsns_year = int(params_copy.get('bsns_year', 0) or 0)
        cur_year = datetime.today().year
        if bsns_year >= cur_year:
            ts_str = str(row[1] or '')[:10]
            today_str = datetime.today().strftime('%Y-%m-%d')
            if ts_str != today_str:
                return None
    return data


def fetch_dart_api(endpoint, params):
    # 1. 캐시 확인
    cached = check_cached_dart_api(endpoint, params)
    if cached is not None:
        return cached

    params_copy = params.copy()
    params_copy.pop('crtfc_key', None)
    params_str = json.dumps(params_copy, sort_keys=True)

    # 2. Thread-safe Rate Limit 슬립
    global _last_api_call_ts
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_api_call_ts
        if elapsed < _MIN_API_INTERVAL:
            time.sleep(_MIN_API_INTERVAL - elapsed)
        _last_api_call_ts = time.time()

    base_url = "https://opendart.fss.or.kr/api"
    full_url = f"{base_url}{endpoint}"

    actual_params = params.copy()
    actual_params['crtfc_key'] = DART_API_KEY

    for attempt in range(2):
        try:
            res = _http_session.get(full_url, params=actual_params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                status = data.get('status')
                # 020(요청제한) 등 일시 오류 시 1회 재시도
                if status in ('020', '800', '900') and attempt == 0:
                    time.sleep(0.8)
                    continue

                # 000(정상) 및 013(데이터 없음) 모두 캐싱하여 재조회 시 수십 초 지연 방지
                # (당해 연도 013은 check_cached_dart_api에서 당일 TTL로 자동 만료 처리됨)
                if status in ('000', '013'):
                    with _db_lock:
                        conn = _get_conn()
                        c = conn.cursor()
                        c.execute(
                            "INSERT OR REPLACE INTO api_cache (endpoint, params, response, timestamp) VALUES (?, ?, ?, ?)",
                            (endpoint, params_str, json.dumps(data), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        )
                        conn.commit()
                        conn.close()
                return data
        except Exception as e:
            if attempt == 0:
                time.sleep(0.5)
                continue
            print(f"DART API request error ({endpoint}, {params_copy}): {e}")
            return None
    return None


def get_historical_prices(stock_code, years=10, force_refresh=False):
    endpoint = "fdr_prices"
    params_str = f"{stock_code}_{years}y_weekly"
    today_str = datetime.today().strftime('%Y-%m-%d')

    if not force_refresh:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("SELECT response, timestamp FROM api_cache WHERE endpoint=? AND params=?", (endpoint, params_str))
        row = c.fetchone()
        conn.close()
        if row and str(row[1] or '')[:10] == today_str:
            try:
                cached_prices = json.loads(row[0])
                if cached_prices:
                    return cached_prices
            except Exception:
                pass

    end_date = datetime.today()
    start_date = end_date.replace(year=end_date.year - years)

    try:
        df = fdr.DataReader(stock_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        if df.empty:
            return []

        # 매주 금요일(주말일) 종가 기준으로 리샘플링하되, 마지막 포인트는 실제 최신 거래일 날짜와 종가를 그대로 반영
        df_weekly = df.resample('W-FRI').last()
        df_weekly = df_weekly.dropna(subset=['Close'])

        prices = []
        for index, row_data in df_weekly.iterrows():
            prices.append({
                'date': index.strftime('%Y-%m-%d'),
                'price': float(row_data['Close'])
            })

        if prices and not df.empty:
            latest_actual_date = df.index[-1].strftime('%Y-%m-%d')
            latest_actual_close = float(df.iloc[-1]['Close'])
            prices[-1]['date'] = latest_actual_date
            prices[-1]['price'] = latest_actual_close

        with _db_lock:
            conn = _get_conn()
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO api_cache (endpoint, params, response, timestamp) VALUES (?, ?, ?, ?)",
                (endpoint, params_str, json.dumps(prices), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            conn.close()
        return prices
    except Exception as e:
        print(f"Error fetching historical prices for {stock_code}: {e}")
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


def _normalize_query_variants(q: str) -> list[str]:
    """입력 쿼리에 대해 공백/대소문자/한영 브랜드 별칭을 변환한 후보 문자열 목록 생성"""
    q_clean = q.strip()
    # "기업명(종목코드)" 또는 "기업명 (종목코드)" 형식 파싱
    m = re.match(r'^(.+?)\s*\(([0-9A-Za-z]{6})\)\s*$', q_clean)
    variants = []
    if m:
        name_part = m.group(1).strip()
        code_part = m.group(2).strip()
        variants.append(code_part)
        variants.append(name_part)
        q_clean = name_part
    else:
        variants.append(q_clean)

    q_nospace = q_clean.replace(" ", "").upper()
    if q_nospace not in variants:
        variants.append(q_nospace)

    # 한 -> 영, 영 -> 한 별칭 치환
    for kor, eng in KOR_TO_ENG_ALIASES:
        if kor in q_nospace:
            v = q_nospace.replace(kor, eng)
            if v not in variants:
                variants.append(v)
        if eng in q_nospace:
            v = q_nospace.replace(eng, kor)
            if v not in variants:
                variants.append(v)

    return variants


def format_corp_display(corp_name: str, stock_code: str) -> str:
    if stock_code:
        return f"{corp_name}({stock_code})"
    return corp_name


def search_corp(query: str):
    if not query or not query.strip():
        return None

    codes = get_corp_codes()
    variants = _normalize_query_variants(query)

    # 1단계: 종목코드 정확히 일치 (6자리 코드 등)
    for v in variants:
        v_up = v.upper()
        for code, name, stock_code in codes:
            if v_up == stock_code.upper():
                return {
                    "corp_code": code,
                    "corp_name": name,
                    "stock_code": stock_code,
                    "display_name": format_corp_display(name, stock_code)
                }

    # 2단계: 기업명 정확히 일치 (대소문자/공백/한영별칭 포함, 최신 modify_date 순)
    for v in variants:
        v_up = v.replace(" ", "").upper()
        for code, name, stock_code in codes:
            name_up = name.replace(" ", "").upper()
            if v_up == name_up:
                return {
                    "corp_code": code,
                    "corp_name": name,
                    "stock_code": stock_code,
                    "display_name": format_corp_display(name, stock_code)
                }

    # 3단계: 접두어(Prefix) 또는 부분 문자열 포함 매칭 (가장 짧은 기업명 우선)
    prefix_matches = []
    substr_matches = []
    for v in variants:
        v_up = v.replace(" ", "").upper()
        if len(v_up) < 2:
            continue
        for code, name, stock_code in codes:
            name_up = name.replace(" ", "").upper()
            if name_up.startswith(v_up):
                prefix_matches.append((len(name_up), code, name, stock_code))
            elif v_up in name_up:
                substr_matches.append((len(name_up), code, name, stock_code))

    if prefix_matches:
        prefix_matches.sort(key=lambda x: x[0])
        _, code, name, stock_code = prefix_matches[0]
        return {
            "corp_code": code,
            "corp_name": name,
            "stock_code": stock_code,
            "display_name": format_corp_display(name, stock_code)
        }

    if substr_matches:
        substr_matches.sort(key=lambda x: x[0])
        _, code, name, stock_code = substr_matches[0]
        return {
            "corp_code": code,
            "corp_name": name,
            "stock_code": stock_code,
            "display_name": format_corp_display(name, stock_code)
        }

    # 4단계: 오타 허용 레벤슈타인 거리 (거리 2 이하)
    best_match = None
    best_dist = float('inf')
    for v in variants:
        v_up = v.replace(" ", "").upper()
        for code, name, stock_code in codes:
            name_up = name.replace(" ", "").upper()
            dist = levenshtein_distance(v_up, name_up)
            if dist < best_dist and dist <= 2:
                best_dist = dist
                best_match = {
                    "corp_code": code,
                    "corp_name": name,
                    "stock_code": stock_code,
                    "display_name": format_corp_display(name, stock_code)
                }

    return best_match


def suggest_corps(query: str, limit: int = 12):
    """검색창 자동완성을 위한 기업명/종목코드 추천 리스트 반환"""
    if not query or not query.strip():
        return []

    codes = get_corp_codes()
    variants = _normalize_query_variants(query)
    seen_stock_codes = set()
    exact_list = []
    prefix_list = []
    substr_list = []

    for code, name, stock_code in codes:
        if not stock_code or stock_code in seen_stock_codes:
            continue
        name_up = name.replace(" ", "").upper()
        sc_up = stock_code.upper()

        matched_tier = 0
        for v in variants:
            v_up = v.replace(" ", "").upper()
            if not v_up:
                continue
            if v_up == name_up or v_up == sc_up:
                matched_tier = 1
                break
            elif name_up.startswith(v_up) or sc_up.startswith(v_up):
                matched_tier = max(matched_tier, 2) if matched_tier == 0 else min(matched_tier, 2)
            elif v_up in name_up or v_up in sc_up:
                if matched_tier == 0:
                    matched_tier = 3

        if matched_tier > 0:
            seen_stock_codes.add(stock_code)
            item = {
                "corp_code": code,
                "corp_name": name,
                "stock_code": stock_code,
                "display_name": format_corp_display(name, stock_code)
            }
            if matched_tier == 1:
                exact_list.append(item)
            elif matched_tier == 2:
                prefix_list.append((len(name), item))
            else:
                substr_list.append((len(name), item))

    prefix_list.sort(key=lambda x: x[0])
    substr_list.sort(key=lambda x: x[0])

    results = exact_list + [x[1] for x in prefix_list] + [x[1] for x in substr_list]
    return results[:limit]


init_db()
