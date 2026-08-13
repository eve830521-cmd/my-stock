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

def parse_financial_data(raw_list):
    extracted = {
        '자산총계': 0, '현금및현금성자산': 0, '단기금융자산': 0, '자본총계': 0,
        '매입채무': 0, '단기금융부채': 0, '매출액': 0, '매출총이익': 0, '영업이익': 0, 
        '지배순이익': 0, '당기순이익': 0, '이자비용': 0, '영업활동현금흐름': 0, 
        '투자활동현금흐름': 0, '재무활동현금흐름': 0, 'CAPEX': 0, '감가상각비': 0,
        '배당금': 0, 'EPS': 0
    }
    found_by_id = set()
    
    capex_pattern = re.compile(r'(유형자산|무형자산|기계장치|토지|건물|구축물|차량운반구|공기구비품).*취득')
    depreciation_pattern = re.compile(r'(감가상각비|무형자산상각비|상각비).*')
    
    for item in raw_list:
        account_id = item.get('account_id', '')
        account_nm = item.get('account_nm', '').replace(' ', '')
        thstrm_amount = item.get('thstrm_amount', '')
        
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
    
    for year in range(int(start_year), int(end_year) + 1):
        for q_name, r_code in REPRT_CODES.items():
            data = get_financial_data(corp_code, str(year), r_code)
            if data:
                parsed = parse_financial_data(data)
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
        df_raw['유통주식수'] = latest_shares
    
    
    df_raw['시가총액'] = df_raw['주가'] * df_raw['유통주식수']
    
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
        if i >= 3:
            for col in flow_columns + ['FCF']:
                sheet3.loc[i, col] = sheet2.loc[i-3:i, col].sum()
                
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
    
    # NaN 값들은 그대로 두어 JSON 시리얼라이즈 시 null로 전달되게 함 (ECharts가 자동 무시하여 차트 안 찌그러짐)
    sheet3 = sheet3.replace([np.inf, -np.inf], np.nan)
    sheet3.drop(columns=['매출액_safe', '자본총계_safe', '지배순이익_safe', '투하자본_safe', '이자비용_safe'], inplace=True)
    
    # Sheet 4: 사업보고서 연간 데이터 (4Q만 추출)
    sheet4 = sheet3[sheet3['Quarter'] == '4Q'].copy().reset_index(drop=True)
    
    # ----------------------------------------------------
    # [NEW] Phase 3: TTM 정상화 EPS 및 월별 밴드 시계열 병합
    # ----------------------------------------------------
    from database import get_historical_prices
    
    # 정상화 EPS 계산: (영업이익 - 법인세) * 지배비율 / 유통주식수
    sheet3['지배비율'] = np.where(sheet3['당기순이익'] != 0, sheet3['지배순이익'] / sheet3['당기순이익'], 1.0)
    sheet3['정상화순이익'] = (sheet3['영업이익'] * (1 - sheet3['법인세율'])) * sheet3['지배비율']
    sheet3['정상화EPS'] = np.where(sheet3['유통주식수'] > 0, sheet3['정상화순이익'] / sheet3['유통주식수'], np.nan)
    sheet3['BPS'] = np.where(sheet3['유통주식수'] > 0, sheet3['자본총계'] / sheet3['유통주식수'], np.nan)
    
    # 분기별 발표일 추정 (1Q: 5-15, 2Q: 8-15, 3Q: 11-15, 4Q: 내년 3-31)
    report_dates = []
    for i, row in sheet3.iterrows():
        y = int(row['Year'])
        q = row['Quarter']
        if q == '1Q': r_date = f"{y}-05-15"
        elif q == '2Q': r_date = f"{y}-08-15"
        elif q == '3Q': r_date = f"{y}-11-15"
        elif q == '4Q': r_date = f"{y+1}-03-31"
        report_dates.append(pd.to_datetime(r_date))
    
    sheet3['ReportDate'] = report_dates
    df_q = sheet3[['ReportDate', '정상화EPS', 'BPS', 'Year', 'Quarter']].copy()
    df_q.set_index('ReportDate', inplace=True)
    
    # 10년 치 주가 가져오기
    prices = get_historical_prices(stock_code, years=10)
    sheet5 = pd.DataFrame()
    sheet6 = pd.DataFrame() # Annual Band
    
    if prices:
        df_prices = pd.DataFrame(prices)
        df_prices['date'] = pd.to_datetime(df_prices['date'])
        df_prices.set_index('date', inplace=True)
        
        # --- 1. TTM 밴드 (월별) ---
        df_combined = pd.concat([df_prices, df_q], axis=1).sort_index()
        df_combined[['정상화EPS', 'BPS', 'Year', 'Quarter']] = df_combined[['정상화EPS', 'BPS', 'Year', 'Quarter']].ffill()
        df_monthly_band = df_combined.loc[df_prices.index].copy()
        df_monthly_band['PER'] = np.where(df_monthly_band['정상화EPS'] > 0, df_monthly_band['price'] / df_monthly_band['정상화EPS'], np.nan)
        df_monthly_band['PBR'] = np.where(df_monthly_band['BPS'] > 0, df_monthly_band['price'] / df_monthly_band['BPS'], np.nan)
        
        valid_per = df_monthly_band['PER'].dropna()
        valid_per = valid_per[valid_per < 120] 
        per_mean = valid_per.mean() if not valid_per.empty else df_monthly_band['PER'].mean()
        per_std = valid_per.std() if len(valid_per) > 1 else df_monthly_band['PER'].std()
        
        valid_pbr = df_monthly_band['PBR'].dropna()
        valid_pbr = valid_pbr[valid_pbr < 10] 
        pbr_mean = valid_pbr.mean() if not valid_pbr.empty else df_monthly_band['PBR'].mean()
        pbr_std = valid_pbr.std() if len(valid_pbr) > 1 else df_monthly_band['PBR'].std()
        
        df_monthly_band['PER_Average'] = per_mean
        df_monthly_band['PER_Plus1SD'] = per_mean + per_std
        df_monthly_band['PER_Minus1SD'] = per_mean - per_std
        df_monthly_band['PER_Max'] = df_monthly_band['PER'].max()
        df_monthly_band['PER_Min'] = df_monthly_band['PER'].min()
        
        df_monthly_band['PBR_Average'] = pbr_mean
        df_monthly_band['PBR_Plus1SD'] = pbr_mean + pbr_std
        df_monthly_band['PBR_Minus1SD'] = pbr_mean - pbr_std
        df_monthly_band['PBR_Max'] = df_monthly_band['PBR'].max()
        df_monthly_band['PBR_Min'] = df_monthly_band['PBR'].min()
        
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
        sheet4['정상화EPS'] = np.where(sheet4['유통주식수'] > 0, sheet4['정상화순이익'] / sheet4['유통주식수'], np.nan)
        sheet4['BPS'] = np.where(sheet4['유통주식수'] > 0, sheet4['자본총계'] / sheet4['유통주식수'], np.nan)
        
        df_annual = sheet4[['Year', '정상화EPS', 'BPS']].copy()
        
        # 12월 말 주가 필터링
        df_prices_dec = df_prices[df_prices.index.month == 12].copy()
        df_prices_dec['Year'] = df_prices_dec.index.year
        df_prices_dec['date_str'] = df_prices_dec.index.strftime('%Y-%m-%d')
        
        # 연도 기준으로 병합
        df_annual_band = pd.merge(df_annual, df_prices_dec, on='Year', how='inner')
        df_annual_band['PER'] = np.where(df_annual_band['정상화EPS'] > 0, df_annual_band['price'] / df_annual_band['정상화EPS'], np.nan)
        df_annual_band['PBR'] = np.where(df_annual_band['BPS'] > 0, df_annual_band['price'] / df_annual_band['BPS'], np.nan)
        
        val_ann_per = df_annual_band['PER'].dropna()
        val_ann_per = val_ann_per[val_ann_per < 120]
        a_per_mean = val_ann_per.mean() if not val_ann_per.empty else df_annual_band['PER'].mean()
        a_per_std = val_ann_per.std() if len(val_ann_per) > 1 else df_annual_band['PER'].std()
        
        val_ann_pbr = df_annual_band['PBR'].dropna()
        val_ann_pbr = val_ann_pbr[val_ann_pbr < 10]
        a_pbr_mean = val_ann_pbr.mean() if not val_ann_pbr.empty else df_annual_band['PBR'].mean()
        a_pbr_std = val_ann_pbr.std() if len(val_ann_pbr) > 1 else df_annual_band['PBR'].std()
        
        df_annual_band['PER_Average'] = a_per_mean
        df_annual_band['PER_Plus1SD'] = a_per_mean + a_per_std
        df_annual_band['PER_Minus1SD'] = a_per_mean - a_per_std
        df_annual_band['PER_Max'] = df_annual_band['PER'].max()
        df_annual_band['PER_Min'] = df_annual_band['PER'].min()
        
        df_annual_band['PBR_Average'] = a_pbr_mean
        df_annual_band['PBR_Plus1SD'] = a_pbr_mean + a_pbr_std
        df_annual_band['PBR_Minus1SD'] = a_pbr_mean - a_pbr_std
        df_annual_band['PBR_Max'] = df_annual_band['PBR'].max()
        df_annual_band['PBR_Min'] = df_annual_band['PBR'].min()
        
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
