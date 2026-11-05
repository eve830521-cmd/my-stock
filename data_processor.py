import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from datetime import datetime
from database import (
    fetch_dart_api,
    check_cached_dart_api,
    search_corp,
    get_historical_prices,
)

REPRT_CODES = {
    "1Q": "11013",
    "2Q": "11012",
    "3Q": "11014",
    "4Q": "11011"
}

Q_ORDER = {"1Q": 1, "2Q": 2, "3Q": 3, "4Q": 4}


def get_tax_rate(income, year):
    """
    국세청 공시 기준 연도별 법인세 한계세율 적용 (과세표준은 당기순이익을 대용치로 사용)
    """
    if income is None or pd.isna(income) or income <= 0:
        return 0.0

    year = int(year)
    if year >= 2023:
        if income <= 200_000_000:
            return 0.09
        elif income <= 20_000_000_000:
            return 0.19
        elif income <= 300_000_000_000:
            return 0.21
        else:
            return 0.24
    else:
        if income <= 200_000_000:
            return 0.10
        elif income <= 20_000_000_000:
            return 0.20
        elif income <= 300_000_000_000:
            return 0.22
        else:
            return 0.25


def get_financial_data(corp_code, bsns_year, reprt_code, preferred_fs=None):
    """
    연결(CFS) 우선 조회 후 없으면 별도(OFS) 조회.
    이미 DB 캐시에 OFS 데이터가 있거나 preferred_fs가 지정된 경우 불필요한 CFS 네트워크 호출을 생략하여 속도 극대화.
    """
    base_params = {
        'corp_code': corp_code,
        'bsns_year': str(bsns_year),
        'reprt_code': reprt_code,
    }

    # 1. 캐시 우선 점검 (CFS -> OFS 순서)
    cfs_params = {**base_params, 'fs_div': 'CFS'}
    ofs_params = {**base_params, 'fs_div': 'OFS'}

    cached_cfs = check_cached_dart_api("/fnlttSinglAcntAll.json", cfs_params)
    if cached_cfs and cached_cfs.get('status') == '000':
        return cached_cfs.get('list', []), 'CFS'

    cached_ofs = check_cached_dart_api("/fnlttSinglAcntAll.json", ofs_params)
    if cached_ofs and cached_ofs.get('status') == '000':
        return cached_ofs.get('list', []), 'OFS'

    # 2. 네트워크 조회 (preferred_fs가 'OFS'이면 OFS 먼저 시도하여 별도 전용 기업의 48회 CFS 실패 호출 방지)
    fs_order = ['OFS', 'CFS'] if preferred_fs == 'OFS' else ['CFS', 'OFS']
    for fs in fs_order:
        params = {**base_params, 'fs_div': fs}
        data = fetch_dart_api("/fnlttSinglAcntAll.json", params)
        if data and data.get('status') == '000':
            return data.get('list', []), fs

    return None, None


def get_alot_matter_dividend(corp_code, bsns_year, reprt_code):
    """
    OpenDART /alotMatter.json (배당에 관한 사항)에서 해당 보고서의 현금배당금총액(원)을 추출.
    정규 사업보고서(결산) 및 분/반기보고서 모두 지원하며, 미지급(-)인 경우 0.0 반환.
    API 호출 실패 시 None 반환하여 기존 CF 기반 fallback 유지.
    """
    params = {
        'corp_code': corp_code,
        'bsns_year': str(bsns_year),
        'reprt_code': reprt_code
    }
    data = fetch_dart_api("/alotMatter.json", params)
    if not data or data.get('status') not in ('000', '013'):
        return None
    if data.get('status') == '013':
        return 0.0

    for item in data.get('list', []):
        se = item.get('se', '').replace(' ', '')
        if '현금배당금총액' in se or '현금배당총액' in se:
            thstrm = item.get('thstrm', '').replace(',', '').strip()
            if thstrm and thstrm != '-':
                try:
                    return float(thstrm) * 1_000_000  # 백만원 -> 원 단위 변환
                except ValueError:
                    pass
            return 0.0

    return 0.0


def get_official_distb_shares(corp_code, bsns_year, reprt_code):
    """
    OpenDART /stockTotqySttus.json (주식의 총수 현황)에서 공식 유통주식수(distb_stock_co)를 추출.
    보통주 기준(없으면 합계 기준) 유통주식수를 반환하며, 실패 시 None 반환.
    """
    params = {
        'corp_code': corp_code,
        'bsns_year': str(bsns_year),
        'reprt_code': reprt_code
    }
    data = fetch_dart_api("/stockTotqySttus.json", params)
    if not data or data.get('status') != '000':
        return None

    items = data.get('list', [])
    # 보통주 우선, 없으면 합계
    for target_se in ('보통주', '합계'):
        for item in items:
            se = item.get('se', '').replace(' ', '')
            if se == target_se:
                for field in ('distb_stock_co', 'istc_totqy'):
                    raw_val = item.get(field, '').replace(',', '').strip()
                    if raw_val and raw_val != '-':
                        try:
                            sh = float(raw_val)
                            if sh > 0:
                                return sh
                        except ValueError:
                            pass
    return None


def _extract_amount(item, sj_div, period='thstrm'):
    """
    period('thstrm' | 'frmtrm' | 'bfefrmtrm')에 맞는 금액 문자열을 파싱하여 float 반환.
    IS/CIS는 누적액(add_amount)을 우선하고, BS/CF는 당기액(amount)을 우선함.
    """
    if period == 'thstrm':
        f_add, f_single = 'thstrm_add_amount', 'thstrm_amount'
    elif period == 'frmtrm':
        f_add, f_single = 'frmtrm_add_amount', 'frmtrm_amount'
    elif period == 'bfefrmtrm':
        f_add, f_single = None, 'bfefrmtrm_amount'
    else:
        f_add, f_single = 'thstrm_add_amount', 'thstrm_amount'

    candidates = []
    if sj_div in ('IS', 'CIS'):
        if f_add:
            candidates.append(item.get(f_add))
        if f_single:
            candidates.append(item.get(f_single))
    else:
        if f_single:
            candidates.append(item.get(f_single))
        if f_add:
            candidates.append(item.get(f_add))

    for raw in candidates:
        if raw is None:
            continue
        s = str(raw).replace(',', '').strip()
        if not s or s == '-':
            continue
        try:
            return float(s)
        except ValueError:
            continue
    return None


def parse_financial_data(raw_list, rcept_no=None, period='thstrm'):
    extracted = {
        '자산총계': 0, '현금및현금성자산': 0, '단기금융자산': 0, '자본총계': 0,
        '매입채무': 0, '단기금융부채': 0, '매출액': 0, '매출총이익': 0, '영업이익': 0,
        '지배순이익': 0, '당기순이익': 0, '이자비용': 0, '영업활동현금흐름': 0,
        '투자활동현금흐름': 0, '재무활동현금흐름': 0, 'CAPEX': 0, '감가상각비': 0,
        '배당금': 0, 'EPS': 0, 'rcept_no': rcept_no,
        '_매출원가': 0, '_판관비': 0, '_순영업손익': 0
    }
    found_by_id = set()

    capex_pattern = re.compile(r'(유형자산|무형자산|기계장치|토지|건물|구축물|차량운반구|공기구비품).*취득')
    depreciation_pattern = re.compile(r'(감가상각비|무형자산상각비|상각비).*')
    footnote_pattern = re.compile(r'(\(주[0-9,\s]+\)|\[주[0-9,\s]+\]|\(단위:[^)]+\))')
    prefix_num_pattern = re.compile(r'^([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩIVX]+|[0-9]+|[가나다라마바사아자차카타파하])[\.\)]\s*')

    for item in raw_list:
        sj_div = item.get('sj_div', '')
        if sj_div not in ('BS', 'IS', 'CIS', 'CF'):
            continue

        val = _extract_amount(item, sj_div, period=period)
        if val is None:
            continue

        account_id = item.get('account_id', '').strip()
        nm_raw = item.get('account_nm', '').replace(' ', '')
        nm = footnote_pattern.sub('', nm_raw)
        nm = prefix_num_pattern.sub('', nm)

        def assign(key, is_id=False):
            if is_id:
                extracted[key] = val
                found_by_id.add(key)
            elif key not in found_by_id:
                if extracted[key] == 0:
                    extracted[key] = val

        def add_val(key, is_id=False, use_abs=False):
            v = abs(val) if use_abs else val
            extracted[key] += v

        if sj_div == 'BS':
            if account_id in ('ifrs-full_Assets', 'ifrs_Assets'):
                assign('자산총계', True)
            elif nm in ('자산총계', '자산합계'):
                assign('자산총계')

            elif account_id in ('ifrs-full_CashAndCashEquivalents', 'ifrs_CashAndCashEquivalents'):
                assign('현금및현금성자산', True)
            elif '현금및현금성자산' in nm or nm == '현금및예치금':
                assign('현금및현금성자산')

            elif account_id in ('ifrs-full_Equity', 'ifrs_Equity'):
                assign('자본총계', True)
            elif nm in ('자본총계', '자본합계'):
                assign('자본총계')

            elif '매입채무' in nm:
                assign('매입채무')

            elif account_id in (
                'ifrs-full_OtherCurrentFinancialAssets', 'ifrs-full_CurrentFinancialAssets',
                'ifrs_OtherCurrentFinancialAssets', 'ifrs_CurrentFinancialAssets'
            ):
                add_val('단기금융자산', True)
            elif '단기금융' in nm or '단기매매증권' in nm or '단기투자자산' in nm:
                add_val('단기금융자산')

            elif account_id in (
                'ifrs-full_OtherCurrentFinancialLiabilities', 'ifrs-full_CurrentFinancialLiabilities',
                'ifrs-full_ShorttermBorrowings', 'ifrs_OtherCurrentFinancialLiabilities',
                'ifrs_CurrentFinancialLiabilities', 'ifrs_ShorttermBorrowings'
            ):
                add_val('단기금융부채', True)
            elif '단기차입금' in nm or '유동성장기부채' in nm or '단기금융부채' in nm:
                add_val('단기금융부채')

        elif sj_div in ('IS', 'CIS'):
            if account_id in ('ifrs-full_Revenue', 'ifrs_Revenue'):
                assign('매출액', True)
            elif nm in ('매출액', '영업수익', '수익(매출액)', '매출', '매출액(영업수익)', '영업수익(매출액)', '매출액합계', '영업수익합계') or nm.startswith('매출액(') or nm.startswith('영업수익('):
                assign('매출액')
            elif nm in ('순영업손익', '순영업수익', '영업순수익'):
                assign('_순영업손익')

            elif account_id in ('ifrs-full_GrossProfit', 'ifrs_GrossProfit'):
                assign('매출총이익', True)
            elif nm.startswith('매출총이익'):
                assign('매출총이익')

            elif account_id in ('ifrs-full_CostOfSales', 'ifrs_CostOfSales') or nm.startswith('매출원가'):
                assign('_매출원가', account_id in ('ifrs-full_CostOfSales', 'ifrs_CostOfSales'))

            elif account_id in (
                'dart_TotalSellingGeneralAdministrativeExpenses',
                'ifrs-full_SellingGeneralAndAdministrativeExpense',
                'ifrs_SellingGeneralAndAdministrativeExpense'
            ) or nm.startswith('판매비와관리비') or nm.startswith('판매및일반관리비') or nm.startswith('판관비'):
                assign('_판관비', account_id != '-표준계정코드 미사용-')

            elif account_id in (
                'dart_OperatingIncomeLoss',
                'ifrs-full_ProfitLossFromOperatingActivities',
                'ifrs_ProfitLossFromOperatingActivities'
            ):
                assign('영업이익', True)
            elif nm.startswith('영업이익') or nm.startswith('영업손실') or nm.startswith('영업손익'):
                assign('영업이익')

            elif account_id in ('ifrs-full_ProfitLoss', 'ifrs_ProfitLoss'):
                assign('당기순이익', True)
            elif any(nm.startswith(p) for p in (
                '당기순이익', '당기순손실', '당기순손익',
                '분기순이익', '분기순손실', '분기순손익',
                '반기순이익', '반기순손실', '반기순손익',
                '연결당기순이익', '연결분기순이익', '연결반기순이익'
            )) and '귀속' not in nm and '지배' not in nm and '비지배' not in nm:
                assign('당기순이익')

            elif account_id in ('ifrs-full_ProfitLossAttributableToOwnersOfParent', 'ifrs_ProfitLossAttributableToOwnersOfParent'):
                assign('지배순이익', True)
            elif 'ComprehensiveIncome' not in account_id and '포괄' not in nm:
                if ('지배기업' in nm or '지배주주' in nm) and ('순이익' in nm or '순손실' in nm or '순손익' in nm or '소유주' in nm):
                    assign('지배순이익')

            if account_id in ('ifrs-full_FinanceCosts', 'ifrs_FinanceCosts', 'dart_InterestExpense', 'ifrs-full_InterestExpense', 'ifrs_InterestExpense'):
                add_val('이자비용', True, True)
            elif '이자비용' in nm and '외' not in nm and '기타' not in nm and '순이자' not in nm:
                add_val('이자비용', False, True)

            if account_id in (
                'ifrs-full_BasicEarningsLossPerShare', 'ifrs_BasicEarningsLossPerShare',
                'ifrs-full_BasicEarningsLossPerShareFromContinuingOperations', 'ifrs_BasicEarningsLossPerShareFromContinuingOperations'
            ):
                eps_val = val / 1_000_000 if abs(val) > 10_000_000 else val
                extracted['EPS'] = eps_val
                found_by_id.add('EPS')
            elif 'EPS' not in found_by_id and extracted['EPS'] == 0:
                if ('기본주당' in nm or '주당순이익' in nm or '주당이익' in nm or '주당손익' in nm) and '희석' not in nm and '우선주' not in nm and '중단' not in nm:
                    eps_val = val / 1_000_000 if abs(val) > 10_000_000 else val
                    extracted['EPS'] = eps_val

        elif sj_div == 'CF':
            if account_id in ('ifrs-full_CashFlowsFromUsedInOperatingActivities', 'ifrs_CashFlowsFromUsedInOperatingActivities'):
                assign('영업활동현금흐름', True)
            elif '영업활동' in nm and '현금' in nm:
                assign('영업활동현금흐름')

            elif account_id in ('ifrs-full_CashFlowsFromUsedInInvestingActivities', 'ifrs_CashFlowsFromUsedInInvestingActivities'):
                assign('투자활동현금흐름', True)
            elif '투자활동' in nm and '현금' in nm:
                assign('투자활동현금흐름')

            elif account_id in ('ifrs-full_CashFlowsFromUsedInFinancingActivities', 'ifrs_CashFlowsFromUsedInFinancingActivities'):
                assign('재무활동현금흐름', True)
            elif '재무활동' in nm and '현금' in nm:
                assign('재무활동현금흐름')

            elif account_id in ('ifrs-full_DividendsPaid', 'ifrs_DividendsPaid'):
                add_val('배당금', True, True)
            elif '배당금의지급' in nm or '배당금지급' in nm:
                add_val('배당금', False, True)

            if capex_pattern.search(nm):
                extracted['CAPEX'] += abs(val)

            if depreciation_pattern.search(nm):
                extracted['감가상각비'] += abs(val)

    # 금융/증권사 등 일반 매출액 계정이 없고 순영업손익만 있는 경우 매출액(영업수익)으로 반영
    if extracted['매출액'] == 0 and extracted['_순영업손익'] != 0:
        extracted['매출액'] = extracted['_순영업손익']

    # 매출총이익이 별도 표기되지 않은 기업 보정 (매출원가 또는 판관비가 있는 경우)
    if extracted['매출총이익'] == 0 and extracted['매출액'] > 0:
        if extracted['_매출원가'] > 0:
            extracted['매출총이익'] = extracted['매출액'] - extracted['_매출원가']
        elif extracted['_판관비'] > 0 and extracted['영업이익'] != 0:
            extracted['매출총이익'] = extracted['영업이익'] + extracted['_판관비']

    if extracted['지배순이익'] == 0:
        extracted['지배순이익'] = extracted['당기순이익']

    extracted.pop('_매출원가', None)
    extracted.pop('_판관비', None)
    extracted.pop('_순영업손익', None)
    return extracted


def _is_future_unfiled_quarter(year: int, q_name: str, now: datetime) -> bool:
    """아직 물리적으로 공시될 수 없는 미래 분기인지 판별하여 불필요한 API 호출 차단"""
    if year > now.year:
        return True
    if year < now.year:
        return False
    # year == now.year 인 경우:
    # 1Q(1~3월)는 4월 이후 공시, 2Q(4~6월)는 7월 이후 공시, 3Q(7~9월)는 10월 이후 공시, 4Q(연간)는 다음해 1월 이후 공시
    min_month = {'1Q': 4, '2Q': 7, '3Q': 10, '4Q': 13}[q_name]
    return now.month < min_month


def _resolve_valid_report_date(year: int, q_name: str, rcept_no) -> pd.Timestamp:
    """
    rcept_no 앞 8자리(YYYYMMDD)를 추출하되, 수년 뒤 제출된 기재정정 보고서로 인해
    시계열 순서가 뒤집히는 현상(Look-ahead / Out-of-order 덮어쓰기)을 방지함.
    """
    default_dates = {
        '1Q': f"{year}-05-15",
        '2Q': f"{year}-08-15",
        '3Q': f"{year}-11-15",
        '4Q': f"{year + 1}-03-31"
    }
    fallback_ts = pd.to_datetime(default_dates.get(q_name, f"{year}-12-31"))

    if rcept_no is None or pd.isna(rcept_no):
        return fallback_ts

    try:
        if isinstance(rcept_no, float):
            r_str = str(int(rcept_no))
        else:
            r_str = str(rcept_no).replace('.0', '').strip()

        if len(r_str) >= 8 and r_str[:8].isdigit():
            r_dt = pd.to_datetime(r_str[:8], format='%Y%m%d')
            # 정상 공시 기간 범위 검증 (기재정정으로 연도가 밀린 경우 법정 기본 공시일 사용)
            if q_name == '1Q' and (r_dt.year == year and 4 <= r_dt.month <= 6):
                return r_dt
            elif q_name == '2Q' and (r_dt.year == year and 7 <= r_dt.month <= 9):
                return r_dt
            elif q_name == '3Q' and (r_dt.year == year and 10 <= r_dt.month <= 12):
                return r_dt
            elif q_name == '4Q' and (r_dt.year == year + 1 and 1 <= r_dt.month <= 4):
                return r_dt
    except Exception:
        pass

    return fallback_ts


def compile_company_data(corp_name_or_query, start_year, end_year):
    corp_info = search_corp(corp_name_or_query)
    if not corp_info:
        return None

    corp_code = corp_info['corp_code']
    official_corp_name = corp_info['corp_name']
    stock_code = corp_info['stock_code']

    # 기존에 종목코드(예: my-list/030190)로 잘못 생성된 폴더가 있다면 공식 기업명 폴더로 정리
    if stock_code and os.path.isdir(f"my-list/{stock_code}") and stock_code != official_corp_name:
        target_dir = f"my-list/{official_corp_name}"
        if not os.path.exists(target_dir):
            try:
                shutil.move(f"my-list/{stock_code}", target_dir)
            except Exception:
                pass
        else:
            try:
                shutil.rmtree(f"my-list/{stock_code}")
            except Exception:
                pass

    now = datetime.today()
    target_quarters = []
    for year in range(int(start_year) - 1, int(end_year) + 1):
        for q_name, r_code in REPRT_CODES.items():
            if not _is_future_unfiled_quarter(year, q_name, now):
                target_quarters.append((year, q_name, r_code))

    # 대표 최신 보고서 1건으로 해당 기업이 CFS(연결)인지 OFS(별도 전용)인지 먼저 파악하여 불필요한 CFS 실패 호출 절감
    preferred_fs = None
    for probe_year in (now.year - 1, now.year - 2, now.year):
        _, fs_detected = get_financial_data(corp_code, str(probe_year), "11011")
        if fs_detected:
            preferred_fs = fs_detected
            break

    raw_by_yq = {}
    parsed_by_yq = {}

    def _fetch_one_quarter(item):
        year, q_name, r_code = item
        data, _ = get_financial_data(corp_code, str(year), r_code, preferred_fs=preferred_fs)
        if not data:
            return None
        rcept_no = data[0].get('rcept_no') if len(data) > 0 else None
        parsed = parse_financial_data(data, rcept_no, period='thstrm')
        parsed['Year'] = year
        parsed['Quarter'] = q_name

        alot_div = get_alot_matter_dividend(corp_code, str(year), r_code)
        if alot_div is not None:
            parsed['배당금'] = alot_div

        return (year, q_name, data, parsed)

    # 병렬 수집 (최대 6 스레드, database.py의 thread-safe rate limiter가 분당 호출 제한 준수)
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(_fetch_one_quarter, target_quarters))

    for res in results:
        if res is not None:
            year, q_name, raw_list, parsed = res
            raw_by_yq[(year, q_name)] = raw_list
            parsed_by_yq[(year, q_name)] = parsed

    if not parsed_by_yq:
        return None

    # [핵심 보완] 전기(frmtrm) 및 전전기(bfefrmtrm) 자동 역추출(Back-fill)
    # 2015년 1Q~3Q(OpenDART 미제공 구간)나 신규 상장/XBRL 전환 직전 연도의 공백을
    # 차기 보고서 내부에 수록된 전기 비교 재무제표(frmtrm)로부터 복원하여 TTM 초기 NaN 공백을 완벽 제거함.
    existing_keys = sorted(list(raw_by_yq.keys()), key=lambda x: (x[0], Q_ORDER[x[1]]))
    for (yr, q_name) in existing_keys:
        raw_list = raw_by_yq[(yr, q_name)]
        prev_key = (yr - 1, q_name)
        if prev_key not in parsed_by_yq and (yr - 1) >= int(start_year) - 1:
            frm_parsed = parse_financial_data(raw_list, rcept_no=None, period='frmtrm')
            if frm_parsed['매출액'] != 0 or frm_parsed['영업이익'] != 0 or frm_parsed['자산총계'] != 0:
                frm_parsed['Year'] = yr - 1
                frm_parsed['Quarter'] = q_name
                alot_prev = get_alot_matter_dividend(corp_code, str(yr - 1), REPRT_CODES[q_name])
                if alot_prev is not None and alot_prev > 0:
                    frm_parsed['배당금'] = alot_prev
                parsed_by_yq[prev_key] = frm_parsed

        # 4Q 사업보고서의 경우 전전기(bfefrmtrm, yr-2) 데이터도 추출 가능
        if q_name == '4Q':
            prev2_key = (yr - 2, '4Q')
            if prev2_key not in parsed_by_yq and (yr - 2) >= int(start_year) - 1:
                bfefrm_parsed = parse_financial_data(raw_list, rcept_no=None, period='bfefrmtrm')
                if bfefrm_parsed['매출액'] != 0 or bfefrm_parsed['영업이익'] != 0 or bfefrm_parsed['자산총계'] != 0:
                    bfefrm_parsed['Year'] = yr - 2
                    bfefrm_parsed['Quarter'] = '4Q'
                    alot_prev2 = get_alot_matter_dividend(corp_code, str(yr - 2), '11011')
                    if alot_prev2 is not None and alot_prev2 > 0:
                        bfefrm_parsed['배당금'] = alot_prev2
                    parsed_by_yq[prev2_key] = bfefrm_parsed

    sorted_keys = sorted(parsed_by_yq.keys(), key=lambda x: (x[0], Q_ORDER[x[1]]))
    raw_data_list = [parsed_by_yq[k] for k in sorted_keys]

    df_raw = pd.DataFrame(raw_data_list)

    # 10년 치 주가 가져오기 (오늘 이미 수집했다면 캐시에서 즉시 반환)
    prices = get_historical_prices(stock_code, years=10) if stock_code else []

    current_price = 0.0
    if prices:
        current_price = float(prices[-1]['price'])
    elif stock_code:
        try:
            import FinanceDataReader as fdr
            recent_date = (datetime.today() - pd.Timedelta(days=14)).strftime('%Y-%m-%d')
            recent_df = fdr.DataReader(stock_code, recent_date)
            if not recent_df.empty:
                current_price = float(recent_df.iloc[-1]['Close'])
        except Exception:
            pass

    df_raw['주가'] = current_price

    # 유통주식수 산출:
    # 1) 지배순이익 / EPS (양수이고 부호가 일치하는 정상 구간에서만 역산하여 음수/이상치 원천 차단)
    def _calc_implied_shares(row):
        eps = row.get('EPS')
        ni_ctrl = row.get('지배순이익')
        if eps and eps != 0 and ni_ctrl and (ni_ctrl * eps > 0):
            sh = ni_ctrl / eps
            if sh > 100_000:  # 최소 상장주식수 안전 필터
                return sh
        return np.nan

    df_raw['유통주식수'] = df_raw.apply(_calc_implied_shares, axis=1)

    # 2) 최신 분기 OpenDART 공식 유통주식수(distb_stock_co) 조회로 정확도 100% 확보
    official_shares = None
    for idx in range(len(df_raw) - 1, max(-1, len(df_raw) - 4), -1):
        r_yr = int(df_raw.loc[idx, 'Year'])
        r_q = df_raw.loc[idx, 'Quarter']
        official_shares = get_official_distb_shares(corp_code, r_yr, REPRT_CODES[r_q])
        if official_shares and official_shares > 0:
            df_raw.loc[df_raw.index[-1], '유통주식수'] = official_shares
            break

    df_raw['유통주식수'] = df_raw['유통주식수'].ffill().bfill().fillna(0)

    # [수정주가 완벽 동기화 패치 유지]
    # 가장 최신(현재)의 유통주식수를 과거 10년치 전체에 일괄 덮어씌움(Broadcast)
    if official_shares and official_shares > 0:
        latest_shares = official_shares
    elif not df_raw['유통주식수'].empty:
        latest_shares = df_raw['유통주식수'].iloc[-1]
    else:
        latest_shares = 0

    df_raw['현재주식수'] = latest_shares
    df_raw['시가총액'] = df_raw['주가'] * df_raw['현재주식수']

    # Sheet 1: 원천 데이터
    sheet1 = df_raw.copy()

    # Sheet 2: 순수 분기 데이터
    sheet2 = sheet1.copy()
    flow_columns = [
        '매출액', '매출총이익', '영업이익', '당기순이익', '지배순이익',
        '영업활동현금흐름', '투자활동현금흐름', '재무활동현금흐름',
        'CAPEX', '감가상각비', '배당금', 'EPS'
    ]

    for i in range(len(sheet2)):
        q = sheet2.loc[i, 'Quarter']
        if q != '1Q' and i > 0:
            prev_row = sheet2.iloc[i - 1]
            if prev_row['Year'] == sheet2.loc[i, 'Year']:
                for col in flow_columns:
                    sheet2.loc[i, col] = sheet1.loc[i, col] - sheet1.iloc[i - 1][col]

    sheet2['순단기금융자산'] = sheet2['단기금융자산'] - sheet2['단기금융부채']
    sheet2['FCF'] = sheet2['영업활동현금흐름'] - sheet2['CAPEX'].abs()

    # Sheet 3: TTM 연환산 데이터
    sheet3 = sheet2.copy()
    for i in range(len(sheet3)):
        current_year = sheet3.loc[i, 'Year']
        current_quarter = sheet3.loc[i, 'Quarter']
        current_cum = sheet1.iloc[i]

        # 4Q(사업보고서)는 그 자체로 이미 1년(4개 분기) 온전한 누적 데이터이므로 전년도 데이터 유무와 무관하게 그대로 사용
        if current_quarter == '4Q':
            for col in flow_columns:
                sheet3.loc[i, col] = current_cum[col]
            # 만약 4Q 배당금이 0이고 전년도 4Q 배당금이 있는 경우에도 4Q는 해당 연도 결산이므로 그대로 둠
            continue

        # 1Q, 2Q, 3Q: 전년도 4분기 누적 및 전년도 동분기 누적 검색
        ly_4q = sheet1[(sheet1['Year'] == current_year - 1) & (sheet1['Quarter'] == '4Q')]
        ly_cq = sheet1[(sheet1['Year'] == current_year - 1) & (sheet1['Quarter'] == current_quarter)]

        if not ly_4q.empty and not ly_cq.empty:
            ly_4q_cum = ly_4q.iloc[0]
            ly_cq_cum = ly_cq.iloc[0]
            for col in flow_columns:
                # 당기 누적 + (전년도 사업보고서 누적 - 전년도 동분기 누적)
                sheet3.loc[i, col] = current_cum[col] + (ly_4q_cum[col] - ly_cq_cum[col])
        else:
            # 과거 1년치 데이터가 온전히 없는 경우 (신규상장 첫해 1~3Q 등) NaN 처리
            for col in flow_columns:
                sheet3.loc[i, col] = np.nan

    # FCF는 연환산된 영업활동현금흐름과 CAPEX로 계산
    sheet3['FCF'] = sheet3['영업활동현금흐름'] - sheet3['CAPEX'].abs()

    # Back-fill 용도로 수집했던 start_year - 1 데이터는 화면 출력을 위해 필터링 (Drop)
    backfill_year = int(start_year) - 1
    sheet1 = sheet1[sheet1['Year'] > backfill_year].reset_index(drop=True)
    sheet2 = sheet2[sheet2['Year'] > backfill_year].reset_index(drop=True)
    sheet3 = sheet3[sheet3['Year'] > backfill_year].reset_index(drop=True)
    # 전기 비교(frmtrm) 역추출로 생성된 보조 분기 중 자체 TTM 손익이 모두 NaN인 행은 Sheet3에서 제외하여 차트 단절 방지
    valid_ttm_rows = sheet3.dropna(subset=['매출액', '영업이익', '당기순이익'], how='all')
    if not valid_ttm_rows.empty:
        sheet3 = valid_ttm_rows.reset_index(drop=True)

    # 분모 0 방어 장치
    sheet3['매출액_safe'] = sheet3['매출액'].replace(0, np.nan)
    sheet3['자본총계_safe'] = sheet3['자본총계'].replace(0, np.nan)
    sheet3['지배순이익_safe'] = sheet3['지배순이익'].replace(0, np.nan)

    # 파생 지표 산출
    sheet3['이익률'] = (sheet3['영업이익'] / sheet3['매출액_safe']) * 100

    # 서비스/플랫폼/IT 기업 등 매출원가/매출총이익 구분 없이 영업수익·영업비용만 공시하는 경우:
    # 매출총이익이 0이면 매출총이익률은 NaN(또는 100% 대신 미표시), 판관비율(영업비용률)은 (매출액 - 영업이익)/매출액으로 산출하여 음수 왜곡 방지
    has_gross_profit = sheet3['매출총이익'] > 0
    sheet3['매출총이익률'] = np.where(
        has_gross_profit,
        (sheet3['매출총이익'] / sheet3['매출액_safe']) * 100,
        np.nan
    )
    sheet3['판관비율'] = np.where(
        has_gross_profit,
        ((sheet3['매출총이익'] - sheet3['영업이익']) / sheet3['매출액_safe']) * 100,
        ((sheet3['매출액'] - sheet3['영업이익']) / sheet3['매출액_safe']) * 100
    )
    sheet3['당기순이익률'] = (sheet3['당기순이익'] / sheet3['매출액_safe']) * 100

    sheet3['ROE'] = (sheet3['지배순이익'] / sheet3['자본총계_safe']) * 100

    # 이자보상배율 무한대 방어
    sheet3['이자비용_safe'] = sheet3['이자비용'].replace(0, np.nan)
    sheet3['이자보상배율'] = sheet3['영업이익'] / sheet3['이자비용_safe']

    # CAPEX / OCF 추가
    sheet3['영업활동현금흐름_safe'] = sheet3['영업활동현금흐름'].apply(lambda x: x if pd.notna(x) and x > 0 else np.nan)
    sheet3['CAPEX_OCF_비율'] = (sheet3['CAPEX'].abs() / sheet3['영업활동현금흐름_safe']) * 100

    # 법인세 및 NOPAT (TTM 기준)
    sheet3['법인세율'] = sheet3.apply(lambda row: get_tax_rate(row['당기순이익'], row['Year']), axis=1)
    sheet3['NOPAT'] = sheet3['영업이익'] * (1 - sheet3['법인세율'])

    # 투하자본 및 ROIC (무한대 방어)
    sheet3['투하자본'] = sheet3['자본총계'] + sheet3['단기금융부채'] - sheet3['현금및현금성자산']
    sheet3['투하자본_safe'] = sheet3['투하자본'].replace(0, np.nan)
    sheet3['ROIC'] = (sheet3['NOPAT'] / sheet3['투하자본_safe']) * 100

    # 밸류에이션 (PER, PBR)
    sheet3['PER'] = sheet3['시가총액'] / sheet3['지배순이익_safe']
    sheet3.loc[sheet3['PER'] < 0, 'PER'] = np.nan
    sheet3['PBR'] = sheet3['시가총액'] / sheet3['자본총계_safe']

    # 배당성향 및 주당배당금(DPS), 배당수익률 추가
    sheet3['배당성향'] = np.where((sheet3['당기순이익'] > 0) & (sheet3['배당금'] > 0), (sheet3['배당금'] / sheet3['당기순이익']) * 100, np.nan)
    sheet3['DPS'] = np.where((sheet3['현재주식수'] > 0) & (sheet3['배당금'] > 0), sheet3['배당금'] / sheet3['현재주식수'], np.nan)
    sheet3['배당수익률'] = np.where((sheet3['주가'] > 0) & (sheet3['DPS'] > 0), (sheet3['DPS'] / sheet3['주가']) * 100, np.nan)

    sheet3 = sheet3.replace([np.inf, -np.inf], np.nan)
    sheet3.drop(columns=['매출액_safe', '자본총계_safe', '지배순이익_safe', '투하자본_safe', '이자비용_safe'], inplace=True)

    # Sheet 4: 사업보고서 연간 데이터 (4Q만 추출)
    sheet4 = sheet3[sheet3['Quarter'] == '4Q'].copy().reset_index(drop=True)

    # ----------------------------------------------------
    # Phase 3: TTM 정상화 EPS 및 주별 밴드 시계열 병합
    # ----------------------------------------------------
    sheet3['지배비율'] = np.where(sheet3['당기순이익'] != 0, sheet3['지배순이익'] / sheet3['당기순이익'], 1.0)
    sheet3['정상화영업이익'] = (sheet3['영업이익'] * (1 - sheet3['법인세율'])) * sheet3['지배비율']

    sheet3['정상화EPS'] = np.where(sheet3['현재주식수'] > 0, sheet3['정상화영업이익'] / sheet3['현재주식수'], np.nan)
    sheet3['BPS'] = np.where(sheet3['현재주식수'] > 0, sheet3['자본총계'] / sheet3['현재주식수'], np.nan)
    sheet3['수정DPS'] = np.where(sheet3['현재주식수'] > 0, sheet3['배당금'] / sheet3['현재주식수'], np.nan)

    report_dates = []
    for _, row in sheet3.iterrows():
        y = int(row['Year'])
        q = row['Quarter']
        r_date = _resolve_valid_report_date(y, q, row.get('rcept_no'))
        report_dates.append(r_date)

    sheet3['ReportDate'] = report_dates
    roe_10y_median = sheet3['ROE'].dropna().median() if not sheet3['ROE'].dropna().empty else 8.0
    sheet3['ROE_10Y_Median'] = roe_10y_median
    sheet4['ROE_10Y_Median'] = roe_10y_median

    df_q = sheet3[['ReportDate', '정상화EPS', 'BPS', '수정DPS', 'Year', 'Quarter', 'ROE', 'ROE_10Y_Median']].copy()
    df_q.sort_values(['Year', 'ReportDate'], inplace=True)
    df_q.set_index('ReportDate', inplace=True)

    sheet5 = pd.DataFrame()
    sheet6 = pd.DataFrame()  # Annual Band

    if prices:
        df_prices = pd.DataFrame(prices)
        df_prices['date'] = pd.to_datetime(df_prices['date'])
        df_prices.set_index('date', inplace=True)

        df_prices = df_prices[~df_prices.index.duplicated(keep='last')]
        df_q = df_q[~df_q.index.duplicated(keep='last')]

        # --- 1. TTM 밴드 (주별) ---
        df_combined = pd.concat([df_prices, df_q], axis=1).sort_index()
        df_combined[['정상화EPS', 'BPS', '수정DPS', 'Year', 'Quarter', 'ROE', 'ROE_10Y_Median']] = (
            df_combined[['정상화EPS', 'BPS', '수정DPS', 'Year', 'Quarter', 'ROE', 'ROE_10Y_Median']].ffill().bfill()
        )
        df_monthly_band = df_combined.loc[df_prices.index].copy()

        df_monthly_band['PER'] = np.where(df_monthly_band['정상화EPS'] > 0, df_monthly_band['price'] / df_monthly_band['정상화EPS'], np.nan)
        df_monthly_band['PBR'] = np.where(df_monthly_band['BPS'] > 0, df_monthly_band['price'] / df_monthly_band['BPS'], np.nan)
        df_monthly_band['배당수익률'] = np.where(
            (df_monthly_band['price'] > 0) & (df_monthly_band['수정DPS'] > 0),
            (df_monthly_band['수정DPS'] / df_monthly_band['price']) * 100,
            np.nan
        )

        valid_per = df_monthly_band['PER'].dropna()
        per_median = valid_per.median() if not valid_per.empty else np.nan
        per_10th = valid_per.quantile(0.1) if not valid_per.empty else np.nan
        per_90th = valid_per.quantile(0.9) if not valid_per.empty else np.nan

        valid_pbr = df_monthly_band['PBR'].dropna()
        pbr_median = valid_pbr.median() if not valid_pbr.empty else np.nan
        pbr_10th = valid_pbr.quantile(0.1) if not valid_pbr.empty else np.nan
        pbr_90th = valid_pbr.quantile(0.9) if not valid_pbr.empty else np.nan

        valid_dy = df_monthly_band['배당수익률'].dropna().loc[lambda x: x > 0]
        dy_median = valid_dy.median() if not valid_dy.empty else np.nan
        dy_10th = valid_dy.quantile(0.1) if not valid_dy.empty else np.nan
        dy_90th = valid_dy.quantile(0.9) if not valid_dy.empty else np.nan

        df_monthly_band['PER_Average'] = per_median
        df_monthly_band['PER_Plus1SD'] = per_90th
        df_monthly_band['PER_Minus1SD'] = per_10th
        df_monthly_band['PER_Max'] = valid_per.max() if not valid_per.empty else np.nan
        df_monthly_band['PER_Min'] = valid_per.min() if not valid_per.empty else np.nan

        df_monthly_band['PBR_Average'] = pbr_median
        df_monthly_band['PBR_Plus1SD'] = pbr_90th
        df_monthly_band['PBR_Minus1SD'] = pbr_10th
        df_monthly_band['PBR_Max'] = valid_pbr.max() if not valid_pbr.empty else np.nan
        df_monthly_band['PBR_Min'] = valid_pbr.min() if not valid_pbr.empty else np.nan

        df_monthly_band['DY_Average'] = dy_median
        df_monthly_band['DY_Plus1SD'] = dy_90th
        df_monthly_band['DY_Minus1SD'] = dy_10th
        df_monthly_band['DY_Max'] = valid_dy.max() if not valid_dy.empty else np.nan
        df_monthly_band['DY_Min'] = valid_dy.min() if not valid_dy.empty else np.nan

        df_monthly_band['Current_ROE'] = df_monthly_band['ROE']
        df_monthly_band['Median_ROE'] = df_monthly_band['ROE_10Y_Median']

        df_monthly_band.reset_index(inplace=True)
        if 'index' in df_monthly_band.columns:
            df_monthly_band['date'] = df_monthly_band['index'].dt.strftime('%Y-%m-%d')
            sheet5 = df_monthly_band.drop(columns=['index'], errors='ignore')
        else:
            df_monthly_band['date'] = df_monthly_band['date'].dt.strftime('%Y-%m-%d')
            sheet5 = df_monthly_band

        # --- 2. 연간(Annual) 밴드 (매년 말 기준) ---
        sheet4['지배비율'] = np.where(sheet4['당기순이익'] != 0, sheet4['지배순이익'] / sheet4['당기순이익'], 1.0)
        sheet4['정상화순이익'] = (sheet4['영업이익'] * (1 - sheet4['법인세율'])) * sheet4['지배비율']
        sheet4['정상화EPS'] = np.where(sheet4['현재주식수'] > 0, sheet4['정상화순이익'] / sheet4['현재주식수'], np.nan)
        sheet4['BPS'] = np.where(sheet4['현재주식수'] > 0, sheet4['자본총계'] / sheet4['현재주식수'], np.nan)
        sheet4['수정DPS'] = np.where(sheet4['현재주식수'] > 0, sheet4['배당금'] / sheet4['현재주식수'], np.nan)

        df_annual = sheet4[['Year', '정상화EPS', 'BPS', '수정DPS', 'ROE', 'ROE_10Y_Median']].copy()

        df_prices_dec = df_prices[df_prices.index.month == 12].copy()
        df_prices_dec['Year'] = df_prices_dec.index.year
        df_prices_dec['date_str'] = df_prices_dec.index.strftime('%Y-%m-%d')
        # 연말 마지막 주 종가 1개만 남김 (아니면 12월 주별 유지)
        df_annual_band = pd.merge(df_annual, df_prices_dec, on='Year', how='inner')
        df_annual_band['PER'] = np.where(df_annual_band['정상화EPS'] > 0, df_annual_band['price'] / df_annual_band['정상화EPS'], np.nan)
        df_annual_band['PBR'] = np.where(df_annual_band['BPS'] > 0, df_annual_band['price'] / df_annual_band['BPS'], np.nan)
        df_annual_band['배당수익률'] = np.where(
            (df_annual_band['price'] > 0) & (df_annual_band['수정DPS'] > 0),
            (df_annual_band['수정DPS'] / df_annual_band['price']) * 100,
            np.nan
        )

        valid_per_a = df_annual_band['PER'].dropna()
        per_median_a = valid_per_a.median() if not valid_per_a.empty else np.nan
        per_10th_a = valid_per_a.quantile(0.1) if not valid_per_a.empty else np.nan
        per_90th_a = valid_per_a.quantile(0.9) if not valid_per_a.empty else np.nan

        valid_pbr_a = df_annual_band['PBR'].dropna()
        pbr_median_a = valid_pbr_a.median() if not valid_pbr_a.empty else np.nan
        pbr_10th_a = valid_pbr_a.quantile(0.1) if not valid_pbr_a.empty else np.nan
        pbr_90th_a = valid_pbr_a.quantile(0.9) if not valid_pbr_a.empty else np.nan

        valid_dy_a = df_annual_band['배당수익률'].dropna().loc[lambda x: x > 0]
        dy_median_a = valid_dy_a.median() if not valid_dy_a.empty else np.nan
        dy_10th_a = valid_dy_a.quantile(0.1) if not valid_dy_a.empty else np.nan
        dy_90th_a = valid_dy_a.quantile(0.9) if not valid_dy_a.empty else np.nan

        df_annual_band['PER_Average'] = per_median_a
        df_annual_band['PER_Plus1SD'] = per_90th_a
        df_annual_band['PER_Minus1SD'] = per_10th_a
        df_annual_band['PER_Max'] = valid_per_a.max() if not valid_per_a.empty else np.nan
        df_annual_band['PER_Min'] = valid_per_a.min() if not valid_per_a.empty else np.nan

        df_annual_band['PBR_Average'] = pbr_median_a
        df_annual_band['PBR_Plus1SD'] = pbr_90th_a
        df_annual_band['PBR_Minus1SD'] = pbr_10th_a
        df_annual_band['PBR_Max'] = valid_pbr_a.max() if not valid_pbr_a.empty else np.nan
        df_annual_band['PBR_Min'] = valid_pbr_a.min() if not valid_pbr_a.empty else np.nan

        df_annual_band['DY_Average'] = dy_median_a
        df_annual_band['DY_Plus1SD'] = dy_90th_a
        df_annual_band['DY_Minus1SD'] = dy_10th_a
        df_annual_band['DY_Max'] = valid_dy_a.max() if not valid_dy_a.empty else np.nan
        df_annual_band['DY_Min'] = valid_dy_a.min() if not valid_dy_a.empty else np.nan

        df_annual_band['Current_ROE'] = df_annual_band['ROE']
        df_annual_band['Median_ROE'] = df_annual_band['ROE_10Y_Median']

        df_annual_band['date'] = df_annual_band['date_str']
        sheet6 = df_annual_band.drop(columns=['date_str'], errors='ignore')

    os.makedirs(f"my-list/{official_corp_name}", exist_ok=True)
    excel_path = f"my-list/{official_corp_name}/Data.xlsx"

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        sheet1.to_excel(writer, sheet_name='Sheet1(Raw)', index=False)
        sheet2.to_excel(writer, sheet_name='Sheet2(Quarterly)', index=False)
        sheet3.drop(columns=['ReportDate'], errors='ignore').to_excel(writer, sheet_name='Sheet3(TTM)', index=False)
        sheet4.drop(columns=['ReportDate'], errors='ignore').to_excel(writer, sheet_name='Sheet4(Annual)', index=False)
        if not sheet5.empty:
            sheet5.to_excel(writer, sheet_name='Sheet5(Band)', index=False)
        if not sheet6.empty:
            sheet6.to_excel(writer, sheet_name='Sheet6(AnnualBand)', index=False)

    return excel_path
