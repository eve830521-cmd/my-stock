import os
import re
import pandas as pd
import urllib.request
from datetime import datetime
from database import fetch_dart_api, search_corp

REPRT_CODES = {
    "1Q": "11013",
    "2Q": "11012",
    "3Q": "11014",
    "4Q": "11011"
}

# (네이버 스크래핑 함수 제거됨)

def get_tax_rate(income, year):
    """
    국세청 공시 기준 연도별 법인세 한계세율 적용 (과세표준은 당기순이익을 대용치로 사용)
    """
    if income <= 0:
        return 0.0
        
    year = int(year)
    if year >= 2023:
        if income <= 200_000_000: return 0.09
        elif income <= 20_000_000_000: return 0.19
        elif income <= 300_000_000_000: return 0.21
        else: return 0.24
    else:
        if income <= 200_000_000: return 0.10
        elif income <= 20_000_000_000: return 0.20
        elif income <= 300_000_000_000: return 0.22
        else: return 0.25

def get_financial_data(corp_code, bsns_year, reprt_code):
    params = {
        'corp_code': corp_code,
        'bsns_year': bsns_year,
        'reprt_code': reprt_code,
        'fs_div': 'CFS'
    }
    data = fetch_dart_api("/fnlttSinglAcntAll.json", params)
    
    if not data or data.get('status') == '013':
        params['fs_div'] = 'OFS'
        data = fetch_dart_api("/fnlttSinglAcntAll.json", params)
        
    if not data or data.get('status') != '000':
        return None
        
    return data.get('list', [])

def parse_financial_data(raw_list, rcept_no=None):
    extracted = {
        '자산총계': 0, '현금및현금성자산': 0, '단기금융자산': 0, '자본총계': 0,
        '매입채무': 0, '단기금융부채': 0, '매출액': 0, '매출총이익': 0, '영업이익': 0, 
        '지배순이익': 0, '당기순이익': 0, '이자비용': 0, '영업활동현금흐름': 0, 
        '투자활동현금흐름': 0, '재무활동현금흐름': 0, 'CAPEX': 0, '감가상각비': 0,
        '배당금': 0, 'EPS': 0, 'rcept_no': rcept_no
    }
    found_by_id = set()
    
    capex_pattern = re.compile(r'(유형자산|무형자산|기계장치|토지|건물|구축물|차량운반구|공기구비품).*취득')
    depreciation_pattern = re.compile(r'(감가상각비|무형자산상각비|상각비).*')
    
    for item in raw_list:
        account_id = item.get('account_id', '')
        account_nm = item.get('account_nm', '').replace(' ', '')
        
        # 누적액 필드(thstrm_add_amount)가 있으면 우선 추출, 없으면 단일액(thstrm_amount) 추출
        thstrm_add_amount = item.get('thstrm_add_amount', '')
        thstrm_amount = thstrm_add_amount if thstrm_add_amount else item.get('thstrm_amount', '')
        
        if not thstrm_amount:
            continue
            
        try:
            val = float(thstrm_amount)
        except ValueError:
            continue
            
        sj_div = item.get('sj_div')
        
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
            if account_id == 'ifrs-full_Assets': assign('자산총계', True)
            elif account_nm == '자산총계': assign('자산총계')
            
            elif account_id == 'ifrs-full_CashAndCashEquivalents': assign('현금및현금성자산', True)
            elif '현금및현금성자산' in account_nm: assign('현금및현금성자산')
            
            elif account_id == 'ifrs-full_Equity': assign('자본총계', True)
            elif account_nm == '자본총계': assign('자본총계')
            
            elif '매입채무' in account_nm: assign('매입채무')
            
            elif account_id in ('ifrs-full_OtherCurrentFinancialAssets', 'ifrs-full_CurrentFinancialAssets'):
                add_val('단기금융자산', True)
            elif '단기금융' in account_nm or '단기매매증권' in account_nm:
                add_val('단기금융자산')
                
            elif account_id in ('ifrs-full_OtherCurrentFinancialLiabilities', 'ifrs-full_CurrentFinancialLiabilities', 'ifrs-full_ShorttermBorrowings'):
                add_val('단기금융부채', True)
            elif '단기차입금' in account_nm or '유동성장기부채' in account_nm:
                add_val('단기금융부채')
                
        elif sj_div in ['IS', 'CIS']:
            if account_id == 'ifrs-full_Revenue': assign('매출액', True)
            elif account_nm in ('매출액', '영업수익', '수익(매출액)'): assign('매출액')
            
            elif account_id == 'ifrs-full_GrossProfit': assign('매출총이익', True)
            elif account_nm.startswith('매출총이익'): assign('매출총이익')
            
            elif account_id == 'dart_OperatingIncomeLoss': assign('영업이익', True)
            elif account_nm.startswith('영업이익') or account_nm.startswith('영업손실'): assign('영업이익')
            
            elif account_id == 'ifrs-full_ProfitLoss': assign('당기순이익', True)
            elif account_nm.startswith('당기순이익') or account_nm.startswith('당기순손실'): assign('당기순이익')
            
            elif account_id == 'ifrs-full_ProfitLossAttributableToOwnersOfParent': assign('지배순이익', True)
            elif '지배기업소유주지분' in account_nm and '당기순이익' in account_nm: assign('지배순이익')
            elif '지배기업의소유주' in account_nm and '당기순이익' in account_nm: assign('지배순이익')
            
            elif account_id in ('ifrs-full_FinanceCosts', 'dart_InterestExpense'): add_val('이자비용', True, True)
            elif '이자비용' in account_nm and '외' not in account_nm and '기타' not in account_nm: add_val('이자비용', False, True)
            
            elif account_id == 'ifrs-full_BasicEarningsLossPerShare': assign('EPS', True)
            elif account_nm.startswith('기본주당이익') or account_nm.startswith('기본주당순이익'): assign('EPS')
            
        elif sj_div == 'CF':
            if account_id == 'ifrs-full_CashFlowsFromUsedInOperatingActivities': assign('영업활동현금흐름', True)
            elif '영업활동' in account_nm and '현금' in account_nm: assign('영업활동현금흐름')
            
            elif account_id == 'ifrs-full_CashFlowsFromUsedInInvestingActivities': assign('투자활동현금흐름', True)
            elif '투자활동' in account_nm and '현금' in account_nm: assign('투자활동현금흐름')
            
            elif account_id == 'ifrs-full_CashFlowsFromUsedInFinancingActivities': assign('재무활동현금흐름', True)
            elif '재무활동' in account_nm and '현금' in account_nm: assign('재무활동현금흐름')
            
            elif account_id == 'ifrs-full_DividendsPaid': add_val('배당금', True, True)
            elif '배당금의지급' in account_nm or '배당금지급' in account_nm: add_val('배당금', False, True)
            
            if capex_pattern.search(account_nm):
                extracted['CAPEX'] += abs(val)
            
            if depreciation_pattern.search(account_nm):
                extracted['감가상각비'] += abs(val)

    if extracted['지배순이익'] == 0:
        extracted['지배순이익'] = extracted['당기순이익']
        
    return extracted

def compile_company_data(corp_name, start_year, end_year):
    corp_info = search_corp(corp_name)
    if not corp_info:
        return None
        
    corp_code = corp_info['corp_code']
    stock_code = corp_info['stock_code']
    
    raw_data_list = []
    
    for year in range(int(start_year) - 1, int(end_year) + 1):
        for q_name, r_code in REPRT_CODES.items():
            data = get_financial_data(corp_code, str(year), r_code)
            if data:
                rcept_no = data[0].get('rcept_no') if len(data) > 0 else None
                parsed = parse_financial_data(data, rcept_no)
                parsed['Year'] = year
                parsed['Quarter'] = q_name
                raw_data_list.append(parsed)
    
    if not raw_data_list:
        return None
        
    df_raw = pd.DataFrame(raw_data_list)
    
    # FinanceDataReader를 이용한 최근 영업일 주가 수집
    current_price = 0
    if stock_code:
        try:
            import FinanceDataReader as fdr
            # 최근 14일치만 가져와서 가장 마지막 영업일의 종가를 선택 (속도 최적화)
            recent_date = (datetime.today() - pd.Timedelta(days=14)).strftime('%Y-%m-%d')
            recent_df = fdr.DataReader(stock_code, recent_date)
            if not recent_df.empty:
                current_price = float(recent_df.iloc[-1]['Close'])
        except Exception:
            pass
            
    df_raw['주가'] = current_price
    
    # EPS 역산법을 활용한 순수 DART 기반 유통주식수 산출 (당기순이익 / EPS)
    import numpy as np
    df_raw['유통주식수'] = df_raw.apply(
        lambda row: (row['당기순이익'] / row['EPS']) if (row.get('EPS') and row['EPS'] != 0) else np.nan, 
        axis=1
    )
    
    # 빈 주식수(EPS 누락된 분기)는 받아온 데이터 내에서 앞뒤 데이터로 채움 (자료 가공)
    df_raw['유통주식수'] = df_raw['유통주식수'].ffill().bfill().fillna(0)
    
    # [수정주가 완벽 동기화 패치]
    # 과거의 액면분할, 유상증자 등이 소급 적용된 '수정 주가'와 과거 재무 데이터를 정확히 매칭하기 위해,
    # 과거의 미수정된 유통주식수를 무시하고 가장 최신(현재)의 유통주식수를 과거 10년치 전체에 일괄 덮어씌웁니다(Broadcast).
    if not df_raw['유통주식수'].empty:
        latest_shares = df_raw['유통주식수'].iloc[-1]
        df_raw['현재주식수'] = latest_shares
    else:
        df_raw['현재주식수'] = 0
        
    df_raw['시가총액'] = df_raw['주가'] * df_raw['현재주식수']
    
    # Sheet 1: 원천 데이터
    sheet1 = df_raw.copy()
    
    # Sheet 2: 순수 분기 데이터
    sheet2 = sheet1.copy()
    flow_columns = ['매출액', '매출총이익', '영업이익', '당기순이익', '지배순이익', '영업활동현금흐름', '투자활동현금흐름', '재무활동현금흐름', 'CAPEX', '감가상각비', '배당금', 'EPS']
    
    for i in range(len(sheet2)):
        q = sheet2.loc[i, 'Quarter']
        if q != '1Q' and i > 0:
            prev_row = sheet2.iloc[i-1]
            if prev_row['Year'] == sheet2.loc[i, 'Year']: 
                for col in flow_columns:
                    sheet2.loc[i, col] = sheet1.loc[i, col] - sheet1.iloc[i-1][col]
                    
    sheet2['순단기금융자산'] = sheet2['단기금융자산'] - sheet2['단기금융부채']
    sheet2['FCF'] = sheet2['영업활동현금흐름'] - sheet2['CAPEX'].abs()
    
    # Sheet 3: TTM 연환산 데이터
    sheet3 = sheet2.copy()
    for i in range(len(sheet3)):
        current_year = sheet3.loc[i, 'Year']
        current_quarter = sheet3.loc[i, 'Quarter']
        
        current_cum = sheet1.iloc[i]
        
        # 전년도 4분기 누적 및 전년도 동분기 누적 검색
        ly_4q = sheet1[(sheet1['Year'] == current_year - 1) & (sheet1['Quarter'] == '4Q')]
        ly_cq = sheet1[(sheet1['Year'] == current_year - 1) & (sheet1['Quarter'] == current_quarter)]
        
        if not ly_4q.empty and not ly_cq.empty:
            ly_4q_cum = ly_4q.iloc[0]
            ly_cq_cum = ly_cq.iloc[0]
            for col in flow_columns:
                # 당기 누적 + (전년도 사업보고서 누적 - 전년도 동분기 누적)
                sheet3.loc[i, col] = current_cum[col] + (ly_4q_cum[col] - ly_cq_cum[col])
        else:
            # 과거 1년치 데이터가 온전히 없는 경우 (신규상장 등) NaN 처리
            import numpy as np
            for col in flow_columns:
                sheet3.loc[i, col] = np.nan
                
    # FCF는 연환산된 영업활동현금흐름과 CAPEX로 계산
    sheet3['FCF'] = sheet3['영업활동현금흐름'] - sheet3['CAPEX'].abs()
    
    # Back-fill 용도로 수집했던 start_year - 1 데이터는 화면 출력을 위해 필터링 (Drop)
    backfill_year = int(start_year) - 1
    sheet1 = sheet1[sheet1['Year'] > backfill_year].reset_index(drop=True)
    sheet2 = sheet2[sheet2['Year'] > backfill_year].reset_index(drop=True)
    sheet3 = sheet3[sheet3['Year'] > backfill_year].reset_index(drop=True)
                
    # 분모 0 방어 장치 (1로 강제 치환하면 시가총액 배수가 되어 차트가 찌그러지므로 NaN으로 처리)
    import numpy as np
    sheet3['매출액_safe'] = sheet3['매출액'].replace(0, np.nan)
    sheet3['자본총계_safe'] = sheet3['자본총계'].replace(0, np.nan)
    sheet3['지배순이익_safe'] = sheet3['지배순이익'].replace(0, np.nan)
    
    # 파생 지표 산출
    sheet3['이익률'] = (sheet3['영업이익'] / sheet3['매출액_safe']) * 100
    sheet3['매출총이익률'] = (sheet3['매출총이익'] / sheet3['매출액_safe']) * 100
    sheet3['판관비율'] = ((sheet3['매출총이익'] - sheet3['영업이익']) / sheet3['매출액_safe']) * 100
    sheet3['당기순이익률'] = (sheet3['당기순이익'] / sheet3['매출액_safe']) * 100
    
    sheet3['ROE'] = (sheet3['지배순이익'] / sheet3['자본총계_safe']) * 100
    
    # 이자보상배율 무한대 방어
    sheet3['이자비용_safe'] = sheet3['이자비용'].replace(0, np.nan)
    sheet3['이자보상배율'] = sheet3['영업이익'] / sheet3['이자비용_safe']
    
    # CAPEX / OCF 추가
    sheet3['영업활동현금흐름_safe'] = sheet3['영업활동현금흐름'].apply(lambda x: x if x > 0 else np.nan)
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
    
    # 배당성향 및 주당배당금(DPS) 추가
    sheet3['배당성향'] = np.where((sheet3['당기순이익'] > 0) & (sheet3['배당금'] > 0), (sheet3['배당금'] / sheet3['당기순이익']) * 100, np.nan)
    sheet3['DPS'] = np.where((sheet3['현재주식수'] > 0) & (sheet3['배당금'] > 0), sheet3['배당금'] / sheet3['현재주식수'], np.nan)

    # NaN 값들은 그대로 두어 JSON 시리얼라이즈 시 null로 전달되게 함 (ECharts가 자동 무시하여 차트 안 찌그러짐)
    sheet3 = sheet3.replace([np.inf, -np.inf], np.nan)
    sheet3.drop(columns=['매출액_safe', '자본총계_safe', '지배순이익_safe', '투하자본_safe', '이자비용_safe'], inplace=True)
    
    # Sheet 4: 사업보고서 연간 데이터 (4Q만 추출)
    sheet4 = sheet3[sheet3['Quarter'] == '4Q'].copy().reset_index(drop=True)
    
    # ----------------------------------------------------
    # [NEW] Phase 3: TTM 정상화 EPS 및 월별 밴드 시계열 병합
    # ----------------------------------------------------
    from database import get_historical_prices
    
    # 정상화 EPS 계산 (Normalized Operating EPS): (영업이익 * (1 - 법인세율)) * 지배비율 / 현재주식수
    sheet3['지배비율'] = np.where(sheet3['당기순이익'] != 0, sheet3['지배순이익'] / sheet3['당기순이익'], 1.0)
    sheet3['정상화영업이익'] = (sheet3['영업이익'] * (1 - sheet3['법인세율'])) * sheet3['지배비율']
    
    # [수정비율(Adjustment Factor) 기반 소급 조정]
    # FDR 수정주가는 액면분할/무상증자를 소급 반영하므로, EPS/BPS도 동일 비율로 소급 조정해야
    # 과거 PER/PBR 비율이 왜곡 없이 유지됨. 최신 주식수(현재주식수)로 나누면 자동 달성.
    sheet3['정상화EPS'] = np.where(sheet3['현재주식수'] > 0, sheet3['정상화영업이익'] / sheet3['현재주식수'], np.nan)
    sheet3['BPS'] = np.where(sheet3['현재주식수'] > 0, sheet3['자본총계'] / sheet3['현재주식수'], np.nan)
    sheet3['수정DPS'] = np.where(sheet3['현재주식수'] > 0, sheet3['배당금'] / sheet3['현재주식수'], np.nan)
    
    report_dates = []
    for i, row in sheet3.iterrows():
        y = int(row['Year'])
        q = row['Quarter']
        
        r_date = None
        if 'rcept_no' in row and pd.notna(row['rcept_no']):
            try:
                # Handle potential float conversion by pandas (e.g., 20230515002335.0)
                r_val = row['rcept_no']
                if isinstance(r_val, float):
                    r_str = str(int(r_val))
                else:
                    r_str = str(r_val).replace('.0', '')
                    
                if len(r_str) >= 14:
                    r_datetime = pd.to_datetime(r_str[:14], format='%Y%m%d%H%M%S')
                    r_date = r_datetime.date()
                    if r_datetime.hour > 15 or (r_datetime.hour == 15 and r_datetime.minute >= 30):
                        r_date = r_date + pd.Timedelta(days=1)
            except Exception:
                pass
                
        if r_date is None:
            if q == '1Q': r_date = f"{y}-05-15"
            elif q == '2Q': r_date = f"{y}-08-15"
            elif q == '3Q': r_date = f"{y}-11-15"
            elif q == '4Q': r_date = f"{y+1}-03-31"
            
        report_dates.append(pd.to_datetime(r_date))
    
    sheet3['ReportDate'] = report_dates
    # 10년 중앙값 ROE 산출을 위해 DataFrame에 추가
    roe_10y_median = sheet3['ROE'].dropna().median() if not sheet3['ROE'].dropna().empty else 8.0
    sheet3['ROE_10Y_Median'] = roe_10y_median
    
    df_q = sheet3[['ReportDate', '정상화EPS', 'BPS', '수정DPS', 'Year', 'Quarter', 'ROE', 'ROE_10Y_Median']].copy()
    df_q.set_index('ReportDate', inplace=True)
    
    # 10년 치 주가 가져오기
    prices = get_historical_prices(stock_code, years=10)
    sheet5 = pd.DataFrame()
    sheet6 = pd.DataFrame() # Annual Band
    
    if prices:
        df_prices = pd.DataFrame(prices)
        df_prices['date'] = pd.to_datetime(df_prices['date'])
        df_prices.set_index('date', inplace=True)
        
        # 중복 인덱스 제거 (Reindexing 오류 방지)
        df_prices = df_prices[~df_prices.index.duplicated(keep='last')]
        df_q = df_q[~df_q.index.duplicated(keep='last')]
        
        # --- 1. TTM 밴드 (월별) ---
        df_combined = pd.concat([df_prices, df_q], axis=1).sort_index()
        df_combined[['정상화EPS', 'BPS', '수정DPS', 'Year', 'Quarter', 'ROE', 'ROE_10Y_Median']] = df_combined[['정상화EPS', 'BPS', '수정DPS', 'Year', 'Quarter', 'ROE', 'ROE_10Y_Median']].ffill()
        df_monthly_band = df_combined.loc[df_prices.index].copy()
        
        # PER은 양수일때만 계산 (음수면 N/A)
        df_monthly_band['PER'] = np.where(df_monthly_band['정상화EPS'] > 0, df_monthly_band['price'] / df_monthly_band['정상화EPS'], np.nan)
        df_monthly_band['PBR'] = np.where(df_monthly_band['BPS'] > 0, df_monthly_band['price'] / df_monthly_band['BPS'], np.nan)
        
        # 배당수익률(%) 계산 (price > 0 및 수정DPS > 0 일 때만 계산)
        df_monthly_band['배당수익률'] = np.where((df_monthly_band['price'] > 0) & (df_monthly_band['수정DPS'] > 0), (df_monthly_band['수정DPS'] / df_monthly_band['price']) * 100, np.nan)
        
        valid_per = df_monthly_band['PER'].dropna()
        # 아웃라이어 필터 제거, 백분위로 처리
        per_median = valid_per.median() if not valid_per.empty else np.nan
        per_10th = valid_per.quantile(0.1) if not valid_per.empty else np.nan
        per_90th = valid_per.quantile(0.9) if not valid_per.empty else np.nan
        
        valid_pbr = df_monthly_band['PBR'].dropna()
        pbr_median = valid_pbr.median() if not valid_pbr.empty else np.nan
        pbr_10th = valid_pbr.quantile(0.1) if not valid_pbr.empty else np.nan
        pbr_90th = valid_pbr.quantile(0.9) if not valid_pbr.empty else np.nan
        
        # 배당수익률 밴드 통계 (배당금 지급된 유효 구간만 필터링)
        valid_dy = df_monthly_band['배당수익률'].dropna().loc[lambda x: x > 0]
        dy_median = valid_dy.median() if not valid_dy.empty else np.nan
        dy_10th = valid_dy.quantile(0.1) if not valid_dy.empty else np.nan # 저배당 / 주가 천장선
        dy_90th = valid_dy.quantile(0.9) if not valid_dy.empty else np.nan # 고배당 / 주가 바닥선 (안전마진)
        
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
        # sheet4(연간 데이터)에 대한 정상화EPS와 BPS 계산 (동일 로직)
        sheet4['지배비율'] = np.where(sheet4['당기순이익'] != 0, sheet4['지배순이익'] / sheet4['당기순이익'], 1.0)
        sheet4['정상화순이익'] = (sheet4['영업이익'] * (1 - sheet4['법인세율'])) * sheet4['지배비율']
        sheet4['정상화EPS'] = np.where(sheet4['현재주식수'] > 0, sheet4['정상화순이익'] / sheet4['현재주식수'], np.nan)
        sheet4['BPS'] = np.where(sheet4['현재주식수'] > 0, sheet4['자본총계'] / sheet4['현재주식수'], np.nan)
        sheet4['수정DPS'] = np.where(sheet4['현재주식수'] > 0, sheet4['배당금'] / sheet4['현재주식수'], np.nan)
        
        df_annual = sheet4[['Year', '정상화EPS', 'BPS', '수정DPS']].copy()
        
        # 12월 말 주가 필터링
        df_prices_dec = df_prices[df_prices.index.month == 12].copy()
        df_prices_dec['Year'] = df_prices_dec.index.year
        df_prices_dec['date_str'] = df_prices_dec.index.strftime('%Y-%m-%d')
        
        # 연도 기준으로 병합
        df_annual_band = pd.merge(df_annual, df_prices_dec, on='Year', how='inner')
        df_annual_band['PER'] = np.where(df_annual_band['정상화EPS'] > 0, df_annual_band['price'] / df_annual_band['정상화EPS'], np.nan)
        df_annual_band['PBR'] = np.where(df_annual_band['BPS'] > 0, df_annual_band['price'] / df_annual_band['BPS'], np.nan)
        
        # 배당수익률(%) 계산 (price > 0 및 수정DPS > 0 일 때만 계산)
        df_annual_band['배당수익률'] = np.where((df_annual_band['price'] > 0) & (df_annual_band['수정DPS'] > 0), (df_annual_band['수정DPS'] / df_annual_band['price']) * 100, np.nan)
        
        valid_per_a = df_annual_band['PER'].dropna()
        per_median_a = valid_per_a.median() if not valid_per_a.empty else np.nan
        per_10th_a = valid_per_a.quantile(0.1) if not valid_per_a.empty else np.nan
        per_90th_a = valid_per_a.quantile(0.9) if not valid_per_a.empty else np.nan
        
        valid_pbr_a = df_annual_band['PBR'].dropna()
        pbr_median_a = valid_pbr_a.median() if not valid_pbr_a.empty else np.nan
        pbr_10th_a = valid_pbr_a.quantile(0.1) if not valid_pbr_a.empty else np.nan
        pbr_90th_a = valid_pbr_a.quantile(0.9) if not valid_pbr_a.empty else np.nan
        
        # 배당수익률 밴드 통계 (배당금 지급된 유효 구간만 필터링)
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
        
        df_annual_band['date'] = df_annual_band['date_str']
        sheet6 = df_annual_band.drop(columns=['date_str'], errors='ignore')
        
    os.makedirs(f"my-list/{corp_name}", exist_ok=True)
    excel_path = f"my-list/{corp_name}/Data.xlsx"
    
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
