import os
import io
import shutil
from datetime import datetime
from urllib.parse import quote
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import pandas as pd
import openpyxl
from database import search_corp, suggest_corps, format_corp_display
from data_processor import compile_company_data

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files mounting (for frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
    return FileResponse("static/index.html")


@app.get("/suggest")
def suggest_company(q: str = Query(""), limit: int = 12):
    """
    기업명 또는 종목코드 자동완성 추천 리스트 반환
    """
    items = suggest_corps(q, limit=limit)
    return {"items": items}


@app.get("/list")
def get_company_list():
    """
    my-list 폴더에 저장된 기업 목록을 "기업명(종목코드)" 형태로 반환
    """
    if not os.path.exists("my-list"):
        return {"companies": [], "company_items": []}

    company_items = []
    seen_corps = set()

    for item in os.listdir("my-list"):
        item_path = os.path.join("my-list", item)
        if not os.path.isdir(item_path):
            continue
        excel_file = os.path.join(item_path, "Data.xlsx")
        if not os.path.exists(excel_file):
            continue

        info = search_corp(item)
        if info:
            official_name = info["corp_name"]
            stock_code = info["stock_code"]
            display_name = info["display_name"]
            # 만약 폴더명이 종목코드(예: 030190)로 되어 있다면 공식 기업명 폴더로 자동 마이그레이션
            if item != official_name:
                target_dir = os.path.join("my-list", official_name)
                if not os.path.exists(target_dir):
                    try:
                        shutil.move(item_path, target_dir)
                    except Exception:
                        pass
        else:
            official_name = item
            stock_code = ""
            display_name = item

        if official_name not in seen_corps:
            seen_corps.add(official_name)
            company_items.append({
                "corp_name": official_name,
                "stock_code": stock_code,
                "display_name": display_name
            })

    company_items.sort(key=lambda x: x["corp_name"])
    companies = [c["display_name"] for c in company_items]
    return {"companies": companies, "company_items": company_items}


def _clean_df_records(df: pd.DataFrame):
    if df is None or df.empty:
        return []
    cleaned = df.replace({pd.NA: None, float("nan"): None, float("inf"): None, float("-inf"): None})
    cleaned = cleaned.where(pd.notnull(cleaned), None)
    return cleaned.to_dict(orient="records")


@app.get("/search")
def search_company(
    corp_name: str = Query(...),
    start_year: int = 2016,
    end_year: int = 2026,
    refresh: bool = False
):
    """
    특정 기업 검색 (기업명, 종목코드, '기업명(종목코드)' 모두 지원)
    - refresh=False 이고 기존 캐시 엑셀(Data.xlsx)이 유효하면 즉시 로드
    - refresh=True 이거나 캐시가 없으면 DART/FDR 수집 및 최신화
    """
    try:
        corp_info = search_corp(corp_name)
        if not corp_info:
            raise HTTPException(
                status_code=404,
                detail=f"'{corp_name}'에 해당하는 상장기업을 찾을 수 없습니다. 기업명 또는 6자리 종목코드를 확인해주세요."
            )

        official_corp_name = corp_info["corp_name"]
        stock_code = corp_info["stock_code"]
        display_name = corp_info["display_name"]
        cached_excel_path = f"my-list/{official_corp_name}/Data.xlsx"

        use_existing_excel = False
        if not refresh and os.path.exists(cached_excel_path):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cached_excel_path))
                # 오늘 이미 생성/최신화된 엑셀 파일인 경우에만 기존 파일 즉시 로드 (당일 주가 및 최신 지표 보장)
                if mtime.date() == datetime.today().date():
                    xl = pd.ExcelFile(cached_excel_path)
                    required_sheets = {"Sheet3(TTM)", "Sheet4(Annual)", "Sheet5(Band)", "Sheet6(AnnualBand)"}
                    if required_sheets.issubset(set(xl.sheet_names)):
                        df_check = xl.parse("Sheet3(TTM)")
                        if not df_check.empty and "DPS" in df_check.columns:
                            use_existing_excel = True
            except Exception:
                use_existing_excel = False

        if use_existing_excel:
            excel_path = cached_excel_path
        else:
            excel_path = compile_company_data(official_corp_name, start_year, end_year)

        if not excel_path or not os.path.exists(excel_path):
            raise HTTPException(
                status_code=404,
                detail=f"'{display_name}'의 재무 데이터를 수집할 수 없습니다."
            )

        df_sheet3 = pd.read_excel(excel_path, sheet_name="Sheet3(TTM)")
        df_sheet4 = pd.read_excel(excel_path, sheet_name="Sheet4(Annual)")

        # 요청 연도 범위 필터링
        if "Year" in df_sheet3.columns:
            df_sheet3 = df_sheet3[(df_sheet3["Year"] >= start_year) & (df_sheet3["Year"] <= end_year)]
        if "Year" in df_sheet4.columns:
            df_sheet4 = df_sheet4[(df_sheet4["Year"] >= start_year) & (df_sheet4["Year"] <= end_year)]

        try:
            df_sheet5 = pd.read_excel(excel_path, sheet_name="Sheet5(Band)")
            band_data = _clean_df_records(df_sheet5)
        except ValueError:
            band_data = []

        try:
            df_sheet6 = pd.read_excel(excel_path, sheet_name="Sheet6(AnnualBand)")
            annual_band_data = _clean_df_records(df_sheet6)
        except ValueError:
            annual_band_data = []

        return {
            "status": "success",
            "corp_name": official_corp_name,
            "stock_code": stock_code,
            "display_name": display_name,
            "ttm_data": _clean_df_records(df_sheet3),
            "annual_data": _clean_df_records(df_sheet4),
            "band_data": band_data,
            "annual_band_data": annual_band_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DCFParams(BaseModel):
    corp_name: str
    current_price: float
    outstanding_shares: int
    terminal_growth_rate: float
    discount_rate: float
    # Scenarios (lists of 5 floats for years 1 to 5)
    positive_revenue_growth: list[float]
    neutral_revenue_growth: list[float]
    negative_revenue_growth: list[float]
    positive_margin: float
    neutral_margin: float
    negative_margin: float
    positive_prob: float
    neutral_prob: float
    negative_prob: float
    n_year_revenue: float
    n_year_tax_rate: float
    net_cash: float


@app.post("/export-dcf")
def export_dcf_excel(params: DCFParams):
    """
    수식(Formula)이 포함된 DCF 3개 시나리오(긍정/중립/부정) 엑셀 파일을 동적으로 생성하여 반환
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DCF Valuation"

    ws["A1"] = "기업명"
    ws["B1"] = params.corp_name

    ws["A2"] = "현재 주가"
    ws["B2"] = params.current_price

    ws["A3"] = "유통주식수"
    ws["B3"] = params.outstanding_shares

    ws["A4"] = "할인율"
    ws["B4"] = params.discount_rate

    ws["A5"] = "영구성장률"
    ws["B5"] = params.terminal_growth_rate

    ws["A6"] = "순현금"
    ws["B6"] = params.net_cash

    ws["A8"] = "N년 매출액"
    ws["B8"] = params.n_year_revenue
    ws["A9"] = "N년 법인세율"
    ws["B9"] = params.n_year_tax_rate

    ws["A11"] = "확률(긍정/중립/부정)"
    ws["B11"] = params.positive_prob
    ws["C11"] = params.neutral_prob
    ws["D11"] = params.negative_prob

    scenarios = [
        ("긍정 시나리오", 13, params.positive_revenue_growth, params.positive_margin),
        ("중립 시나리오", 21, params.neutral_revenue_growth, params.neutral_margin),
        ("부정 시나리오", 29, params.negative_revenue_growth, params.negative_margin),
    ]

    for title, base_row, growth_list, margin_val in scenarios:
        ws[f"A{base_row}"] = title
        for idx, label in enumerate(["N+1", "N+2", "N+3", "N+4", "N+5"]):
            ws.cell(row=base_row, column=2 + idx, value=label)

        r_growth = base_row + 1
        ws[f"A{r_growth}"] = "매출성장률(입력)"
        for i, rate in enumerate(growth_list[:5]):
            ws.cell(row=r_growth, column=2 + i, value=rate)

        r_margin = base_row + 2
        ws[f"A{r_margin}"] = "영업이익률(입력)"
        ws[f"B{r_margin}"] = margin_val

        r_rev = base_row + 3
        ws[f"A{r_rev}"] = "예상 매출액"
        ws[f"B{r_rev}"] = f"=B8*(1+B{r_growth})"
        ws[f"C{r_rev}"] = f"=B{r_rev}*(1+C{r_growth})"
        ws[f"D{r_rev}"] = f"=C{r_rev}*(1+D{r_growth})"
        ws[f"E{r_rev}"] = f"=D{r_rev}*(1+E{r_growth})"
        ws[f"F{r_rev}"] = f"=E{r_rev}*(1+F{r_growth})"

        r_nopat = base_row + 4
        ws[f"A{r_nopat}"] = "예상 세후영업이익"
        for i in range(5):
            col = chr(ord("B") + i)
            ws[f"{col}{r_nopat}"] = f"={col}{r_rev}*$B${r_margin}*(1-$B$9)"

        ws[f"H{r_rev}"] = "영구가치"
        ws[f"H{r_nopat}"] = f"=F{r_nopat}*(1+$B$5)/($B$4-$B$5)"

        r_pv = base_row + 5
        ws[f"A{r_pv}"] = "현가 합계"
        ws[f"B{r_pv}"] = (
            f"=(B{r_nopat}/((1+$B$4)^1)) + (C{r_nopat}/((1+$B$4)^2)) + "
            f"(D{r_nopat}/((1+$B$4)^3)) + (E{r_nopat}/((1+$B$4)^4)) + "
            f"(F{r_nopat}/((1+$B$4)^5)) + (H{r_nopat}/((1+$B$4)^5))"
        )

    # 최종 내재가치 (3개 시나리오 가중평균)
    ws["A37"] = "최종 내재가치 총합 (가중평균)"
    ws["B37"] = "=(B18*B11) + (B26*C11) + (B34*D11)"

    ws["A38"] = "적정 시가총액"
    ws["B38"] = "=B37 + B6"

    ws["A39"] = "적정 주가"
    ws["B39"] = "=B38 / B3"

    ws["A40"] = "기대수익률(연평균)"
    ws["B40"] = "=(B39/B2)^(1/5) - 1"

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    encoded_filename = quote(f"{params.corp_name}_DCF.xlsx")
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )
