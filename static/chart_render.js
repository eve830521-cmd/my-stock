let globalChartData = null;
let charts = [];

const chartExplanations = {
    0: { // 1번 차트
        title: "1. 실적 추이",
        purpose: "기업의 외형(매출) 성장과 실제 이익 규모의 장기적 추세를 직관적으로 파악합니다.",
        action: "시클리컬 기업의 이익 사이클 주기를 확인하여 현재 실적이 바닥인지, 호황기 고점인지 판단합니다."
    },
    1: { // 2번 차트
        title: "2. 매출액 & 이익률",
        purpose: "외형 성장과 수익성(마진)이 함께 상승하는지 동행성을 점검합니다.",
        action: "악화되던 이익률이 바닥을 찍고 턴어라운드(Turn-around)하는 시점을 포착하는 데 유용합니다."
    },
    2: { // 3번 차트
        title: "3. 이익 구조 (매출총이익률 & 판관비율)",
        purpose: "기업의 원가 경쟁력과 고정비(판관비) 통제 능력을 파악합니다.",
        action: "매출총이익률은 유지되는데 판관비율만 증가했다면, 향후 불황이 끝나고 매출 회복 시 '영업레버리지' 효과로 이익이 급증할 수 있음을 암시합니다."
    },
    3: { // 4번 차트
        title: "4. 이익 및 현금흐름 퀄리티",
        purpose: "장부상 이익(영업이익)과 실제 통장에 꽂힌 현금(OCF)의 괴리를 점검합니다.",
        action: "흑자부도 위험을 방지합니다. 흑자인데 영업활동현금흐름이 마이너스(-)라면 분식회계나 자금 압박 리스크를 의심해야 합니다."
    },
    4: { // 5번 차트
        title: "5. 이자보상배율 (안전성)",
        purpose: "기업의 부채 상환 능력 및 파산 위험을 점검합니다.",
        action: "이자보상배율이 1 미만이면 번 돈으로 이자도 못 낸다는 의미입니다. 특히 불황(다운사이클)을 버틸 재무적 체력이 있는지 검증합니다."
    },
    5: { // 6번 차트
        title: "6. 잉여 자금 및 실적",
        purpose: "기업의 실질적인 여유 현금력(안전마진)을 파악합니다.",
        action: "시가총액 대비 순현금 비중이 높을수록 하방 경직성이 강합니다. 불황기에도 버티기가 가능한 든든한 체력을 의미합니다."
    },
    6: { // 7번 차트
        title: "7. 현금흐름 3대 지표",
        purpose: "우량 기업의 정석적인 현금 운용 패턴 '영업(+), 투자(-), 재무(-)'인지 확인합니다.",
        action: "불황기에 돈을 벌지 못해(영업-) 자산을 팔거나(투자+) 빚을 내는(재무+) 등 현금흐름 악화 패턴이 나타나는지 경계합니다."
    },
    7: { // 8번 차트
        title: "8. 자본 효율성 (ROE, ROIC, PBR)",
        purpose: "주주의 자본을 굴리는 효율성(ROE)과 시장의 가격 평가(PBR)를 비교합니다.",
        action: "구조적 수익성이 높은 우량 기업이 일시적인 불황으로 ROE와 PBR이 동반 폭락했을 때가 훌륭한 매수 기회입니다."
    },
    8: { // 9번 차트
        title: "9. 영업활동현금흐름 대비 재투자 (CAPEX/OCF)",
        purpose: "번 돈 대비 설비투자에 얼마나 과도하게 돈을 쓰는지 자본 배분을 점검합니다.",
        action: "100%를 지속 초과하면 외부 차입이 강제됩니다. 안정적으로 통제되며 잉여현금(FCF)을 축적하는지 확인합니다."
    },
    9: { // 10번 차트
        title: "10. 주가수익비율 (PER) 밴드",
        purpose: "이익(정상화EPS) 기준 현재 주가의 절대적 저평가/고평가 국면을 판단합니다.",
        action: "시클리컬 기업은 이익이 급증해 'PER이 낮아 보일 때'가 고점일 수 있습니다. 10년 중앙값을 활용해 착시를 제거하고 하위 10% 부근에서 매수 기회를 찾습니다."
    },
    10: { // 11번 차트
        title: "11. 주가순자산비율 (PBR) 밴드",
        purpose: "자산(BPS) 기준 현재 주가의 밸류에이션을 점검합니다. (시클리컬 투자의 핵심 지표)",
        action: "자산은 이익보다 변동성이 적어 든든한 기준점이 됩니다. 10년 평균 ROE가 훼손되지 않은 우량주가 역사적 최저점이나 하위 10% 밴드에 도달했을 때 적극적인 매수를 고려합니다."
    },
    11: { // 12번 차트
        title: "12. 주가배당수익률 (Dividend Yield) 밴드",
        purpose: "역사적 배당수익률의 상단/하단 밴드를 통해 주가의 배당 안전마진과 고평가/저평가 구간을 판단합니다.",
        action: "배당수익률이 상위 10% 밴드(고배당 구간)에 도달했을 때는 배당 하방 지지력이 강력한 안전마진 매수 기회입니다. 반대로 하위 10% 밴드(저배당 구간)는 주가 고평가 신호로 활용합니다."
    },
    12: { // 5-1번 차트
        title: "5-1. 연간 배당총액 및 배당성향 (안전성)",
        purpose: "기업의 장기 배당 정책의 지속성과 성장성, 그리고 당기순이익 대비 연간 배당총액 지급 비율(배당성향)을 확인합니다.",
        action: "연간 배당총액이 삭감 없이 꾸준히 유지/증가하는지 확인하고, 배당성향이 과도하게 높아(예: 80% 초과) 이익 체력을 넘어서는 무리한 배당인지, 아니면 실적 기반의 안정적 배당인지 판별합니다. 현재의 고배당수익률이 일시적인지 구조적인지 검증하는 데 필수적입니다."
    }
};

function showChartModal(chartIndex) {
    const info = chartExplanations[chartIndex];
    if (!info) return;
    document.getElementById('chartModalTitle').textContent = info.title;
    document.getElementById('chartModalPurpose').textContent = info.purpose;
    document.getElementById('chartModalAction').textContent = info.action;
    document.getElementById('chartInfoModal').classList.add('show');
}

function closeChartModal() {
    document.getElementById('chartInfoModal').classList.remove('show');
}

document.addEventListener('click', function(e) {
    const modal = document.getElementById('chartInfoModal');
    if (e.target === modal) {
        closeChartModal();
    }
});

let currentMode = 'TTM'; // 'TTM' or 'Annual'
let syncBandPeriods = true;
let currentBandMonths = { 9: 'all', 10: 'all', 11: 'all' };
let isSyncingZoom = false;

function toggleSyncBands(checked) {
    syncBandPeriods = checked;
    let syncCb = document.getElementById('syncBandCheckbox');
    if (syncCb) syncCb.checked = checked;
    if (syncBandPeriods) {
        let perMonths = currentBandMonths[9] || 'all';
        setBandPeriod(10, perMonths, true);
        setBandPeriod(11, perMonths, true);
    }
}

function setBandPeriod(chartIndex, months, fromSync = false) {
    let bandData = window.currentBandData;
    if (!bandData || bandData.length === 0) return;
    
    currentBandMonths[chartIndex] = months;
    
    let lastItem = bandData[bandData.length - 1];
    let lastDateStr = lastItem.date || (lastItem.Year ? `${lastItem.Year}-12-31` : null);
    let endDate = lastDateStr ? new Date(lastDateStr) : new Date();
    
    let firstItem = bandData[0];
    let firstDateStr = firstItem.date || (firstItem.Year ? `${firstItem.Year}-01-01` : null);
    let startDateAll = firstDateStr ? new Date(firstDateStr) : new Date();
    let totalMonths = Math.max(1, Math.round((endDate - startDateAll) / (1000 * 60 * 60 * 24 * 30.4375)));

    let startPercent = 0;
    let endPercent = 100;
    let startIdx = 0;
    let endIdx = bandData.length - 1;
    let isFull = false;
    let effectiveMonths = totalMonths;

    if (months === 'all' || !months || months <= 0 || parseInt(months) >= totalMonths) {
        startPercent = 0;
        endPercent = 100;
        startIdx = 0;
        isFull = true;
        effectiveMonths = totalMonths;
    } else {
        let m = parseInt(months);
        effectiveMonths = m;
        let targetStartDate = new Date(endDate);
        targetStartDate.setMonth(targetStartDate.getMonth() - m);
        
        startIdx = bandData.findIndex(d => {
            let cur = new Date(d.date || `${d.Year}-01-01`);
            return cur >= targetStartDate;
        });
        if (startIdx === -1) startIdx = 0;
        startPercent = (startIdx / Math.max(1, bandData.length - 1)) * 100;
        endPercent = 100;
    }
    
    let chart = charts[chartIndex];
    if (chart) {
        chart.setOption({
            dataZoom: [
                { type: 'inside', start: startPercent, end: endPercent },
                { type: 'slider', start: startPercent, end: endPercent }
            ]
        });
        
        if (typeof window.updateBandChart === 'function') {
            window.updateBandChart(chartIndex);
        }
    }
    
    let actualStart = bandData[startIdx].date || bandData[startIdx].Year;
    let actualEnd = bandData[endIdx].date || bandData[endIdx].Year;
    updateBandPeriodUI(chartIndex, effectiveMonths, actualStart, actualEnd, isFull);
    
    // 동기화 처리 (9, 10, 11번 밴드)
    if (syncBandPeriods && !fromSync) {
        [9, 10, 11].forEach(targetIndex => {
            if (targetIndex !== chartIndex) {
                setBandPeriod(targetIndex, months, true);
            }
        });
    }
}

function applyCustomMonths(chartIndex) {
    let inputId = chartIndex === 9 ? 'perMonthsInput' : (chartIndex === 10 ? 'pbrMonthsInput' : 'dyMonthsInput');
    let input = document.getElementById(inputId);
    if (!input || !input.value) return;
    let val = parseInt(input.value.trim());
    if (isNaN(val) || val <= 0) {
        alert("1 이상의 개월 수를 입력해주세요.");
        return;
    }
    setBandPeriod(chartIndex, val);
}

function updateBandPeriodUI(chartIndex, effectiveMonths, startDateStr, endDateStr, isFull) {
    let prefix = chartIndex === 9 ? 'per' : (chartIndex === 10 ? 'pbr' : 'dy');
    let badge = document.getElementById(`${prefix}PeriodBadge`);
    let input = document.getElementById(`${prefix}MonthsInput`);
    let presetContainer = document.getElementById(`${prefix}PresetBtns`);
    
    if (badge) {
        if (isFull) {
            badge.textContent = `조회기간: 전체 ${effectiveMonths}개월 (${startDateStr} ~ ${endDateStr})`;
        } else {
            badge.textContent = `조회기간: 최근 ${effectiveMonths}개월 (${startDateStr} ~ ${endDateStr})`;
        }
    }
    
    if (input) {
        input.value = isFull ? '' : effectiveMonths;
    }
    
    if (presetContainer) {
        let buttons = presetContainer.querySelectorAll('.btn-period');
        buttons.forEach(btn => {
            let onclickText = btn.getAttribute('onclick') || '';
            if (isFull && onclickText.includes("'all'")) {
                btn.classList.add('active');
            } else if (!isFull && onclickText.includes(`, ${effectiveMonths})`)) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // 13개 차트 초기화 (다크모드 테마 적용)
    const chartIdList = [
        'chart1', 'chart2', 'chart3', 'chart4', 'chart5',
        'chart6', 'chart7', 'chart8', 'chart9', 'chart10',
        'chart11', 'chart12', 'chart5_1'
    ];
    
    chartIdList.forEach((id, idx) => {
        let chartDom = document.getElementById(id);
        if (chartDom) {
            let chart = echarts.init(chartDom, 'dark');
            charts[idx] = chart;

            chart.on('click', function(params) {
                if (params.componentType === 'title') {
                    showChartModal(idx);
                }
            });
        }
    });
    
    // 토글 스위치 이벤트 리스너 추가
    const toggle = document.getElementById('dataModeToggle');
    if (toggle) {
        toggle.addEventListener('change', (e) => {
            currentMode = e.target.checked ? 'Annual' : 'TTM';
            document.getElementById('label-ttm').classList.toggle('active', !e.target.checked);
            document.getElementById('label-annual').classList.toggle('active', e.target.checked);
            
            if (globalChartData) {
                renderCharts(currentMode === 'TTM' ? globalChartData.ttm_data : globalChartData.annual_data);
            }
        });
    }

    // 윈도우 리사이즈 시 차트 리사이즈
    window.addEventListener('resize', () => {
        charts.forEach(c => c.resize());
    });

    document.getElementById('searchBtn').addEventListener('click', () => {
        const corpName = document.getElementById('corpInput').value;
        const startYear = document.getElementById('startYear').value;
        const endYear = document.getElementById('endYear').value;
        
        if (!corpName) return alert("기업명을 입력하세요.");
        searchData(corpName, startYear, endYear);
    });

    // 엔터키 검색
    document.getElementById('corpInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') document.getElementById('searchBtn').click();
    });

    loadCompanyList();
});

async function loadCompanyList() {
    try {
        const res = await fetch('/list');
        const data = await res.json();
        const ul = document.getElementById('companyList');
        if (!ul) return;
        ul.innerHTML = '';
        data.companies.forEach(company => {
            let li = document.createElement('li');
            li.textContent = company;
            li.onclick = () => {
                document.getElementById('corpInput').value = company;
                document.getElementById('searchBtn').click();
            };
            ul.appendChild(li);
        });
    } catch (e) {
        console.error("Failed to load list", e);
    }
}

async function searchData(corpName, startYear, endYear) {
    const overlay = document.getElementById('loadingOverlay');
    try {
        overlay.style.display = 'flex'; // 로딩 켜기
        
        const res = await fetch(`/search?corp_name=${encodeURIComponent(corpName)}&start_year=${startYear}&end_year=${endYear}`);
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "데이터를 불러오지 못했습니다.");
        }
        
        const data = await res.json();
        globalChartData = data;
        
                document.getElementById('currentCorpName').textContent = data.corp_name;
        
        let badge = document.getElementById('latestReportBadge');
        if (badge && data.ttm_data && data.ttm_data.length > 0) {
            let lastData = data.ttm_data[data.ttm_data.length - 1];
            let qText = lastData.Quarter;
            if (qText === '2Q') qText = '반기';
            else if (qText === '4Q') qText = '사업보고서';
            badge.textContent = `최신: ${lastData.Year}년 ${qText}`;
            badge.style.display = 'inline-block';
        }
        
        renderCharts(currentMode === 'TTM' ? data.ttm_data : data.annual_data);
        
        if (typeof renderDcfTab === 'function') {
            renderDcfTab(data);
        }
        
        loadCompanyList();
        
    } catch (e) {
        alert("오류: " + e.message);
    } finally {
        overlay.style.display = 'none'; // 로딩 끄기
    }
}

function renderCharts(viewData) {
    if (!viewData || viewData.length === 0) return;

    let xAxisData = viewData.map(d => d.Year + (currentMode === 'TTM' ? '.' + d.Quarter : ''));
    
    const yAxisFormatter = (value) => {
        if (Math.abs(value) >= 1000000000000) {
            return (value / 1000000000000).toFixed(1) + '조';
        } else if (Math.abs(value) >= 100000000) {
            return (value / 100000000).toFixed(0) + '억';
        } else if (Math.abs(value) >= 10000) {
            return (value / 10000).toFixed(0) + '만';
        }
        return value.toLocaleString();
    };

    const commonOptions = {
        backgroundColor: 'transparent',
        tooltip: { 
            trigger: 'axis', 
            axisPointer: { type: 'cross' },
            valueFormatter: (value) => {
                if (value == null || isNaN(value)) return '-';
                if (Math.abs(value) >= 1000000000000) return (value / 1000000000000).toFixed(1) + '조';
                if (Math.abs(value) >= 100000000) return (value / 100000000).toFixed(0) + '억';
                if (Math.abs(value) >= 10000) return (value / 10000).toFixed(0) + '만';
                return value.toLocaleString();
            }
        },
        legend: { top: '5%' },
        grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            { type: 'slider', start: 0, end: 100, bottom: '2%' }
        ]
    };

    const applyOption = (chartIndex, title, optionOverrides) => {
        if (!charts[chartIndex]) return;
        
        if (optionOverrides.series) {
            optionOverrides.series = optionOverrides.series.map(s => {
                if (s.type === 'line') {
                    return { smooth: true, ...s };
                }
                return s;
            });
        }

        charts[chartIndex].setOption({
            title: { text: title, left: 'center', top: 0, triggerEvent: true },
            ...commonOptions,
            ...optionOverrides
        }, true);
    };

    const round2 = (val) => (val != null && typeof val === 'number' && !isNaN(val)) ? Math.round(val * 100) / 100 : null;

    // 1. 실적 차트 (매출액, 영업이익, 당기순이익)
    applyOption(0, '1. 실적 추이', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: [
            { type: 'value', name: '매출액', axisLabel: { formatter: yAxisFormatter }, scale: true },
            { type: 'value', name: '이익', axisLabel: { formatter: yAxisFormatter }, scale: true, splitLine: { show: false } }
        ],
        series: [
            { name: '매출액', type: 'bar', data: viewData.map(d => d['매출액']) },
            { name: '영업이익', type: 'line', yAxisIndex: 1, data: viewData.map(d => d['영업이익']) },
            { name: '당기순이익', type: 'line', yAxisIndex: 1, data: viewData.map(d => d['당기순이익']) }
        ]
    });

    // 2. 매출액 & 이익률
    applyOption(1, '2. 매출액 & 이익률', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: [
            { type: 'value', name: '매출액(원)', axisLabel: { formatter: yAxisFormatter }, scale: true },
            { type: 'value', name: '이익률(%)', scale: true, splitLine: { show: false } }
        ],
        series: [
            { name: '매출액', type: 'bar', data: viewData.map(d => d['매출액']) },
            { name: '매출총이익률', type: 'line', yAxisIndex: 1, data: viewData.map(d => round2(d['매출총이익률'])) },
            { name: '영업이익률', type: 'line', yAxisIndex: 1, data: viewData.map(d => round2(d['이익률'])) }
        ]
    });

    // 3. 매출총이익률 & 판관비율
    applyOption(2, '3. 이익 구조 (매출총이익률 & 판관비율)', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value', name: '비율(%)', scale: true },
        series: [
            { name: '매출총이익률', type: 'line', data: viewData.map(d => round2(d['매출총이익률'])) },
            { name: '판관비율', type: 'line', data: viewData.map(d => round2(d['판관비율'])) }
        ]
    });

    // 4. 이익 & 현금흐름
    applyOption(3, '4. 이익 및 현금흐름 퀄리티', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value', axisLabel: { formatter: yAxisFormatter }, scale: true },
        series: [
            { name: '영업이익', type: 'bar', data: viewData.map(d => d['영업이익']) },
            { name: '영업활동현금흐름', type: 'line', data: viewData.map(d => d['영업활동현금흐름']) }
        ]
    });

    // 5. 이자보상배율
    applyOption(4, '5. 이자보상배율 (안전성)', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value', name: '배율', scale: true },
        series: [
            { name: '이자보상배율', type: 'line', data: viewData.map(d => round2(d['이자보상배율'])), areaStyle: {} }
        ]
    });

    // 5-1. 연간 배당금 및 배당성향 (안전성)
    let annualList = (globalChartData && globalChartData.annual_data && globalChartData.annual_data.length > 0)
        ? globalChartData.annual_data
        : viewData.filter(d => !d.Quarter || d.Quarter === '4Q');
    
    let divXAxis = annualList.map(d => (d.Year ? d.Year + '년' : '-'));
    applyOption(12, '5-1. 연간 배당총액 및 배당성향 (안전성)', {
        xAxis: { type: 'category', data: divXAxis },
        yAxis: [
            { type: 'value', name: '연간 배당총액(원)', axisLabel: { formatter: yAxisFormatter }, scale: true },
            { type: 'value', name: '배당성향(%)', axisLabel: { formatter: '{value}%' }, scale: true, splitLine: { show: false } }
        ],
        series: [
            {
                name: '연간 배당총액',
                type: 'bar',
                data: annualList.map(d => d['배당금'] || 0),
                itemStyle: { color: '#5470c6' },
                tooltip: { valueFormatter: (val) => val != null ? val.toLocaleString() + '원' : '-' }
            },
            {
                name: '배당성향',
                type: 'line',
                yAxisIndex: 1,
                data: annualList.map(d => (d['당기순이익'] > 0 && d['배당금'] > 0) ? round2((d['배당금'] / d['당기순이익']) * 100) : (d['배당성향'] != null ? round2(d['배당성향']) : null)),
                lineStyle: { color: '#fac858', width: 3 },
                itemStyle: { color: '#fac858' },
                tooltip: { valueFormatter: (val) => val != null ? val + '%' : '-' }
            }
        ]
    });

    // 6. 순 단기금융자산 & 당기순이익
    applyOption(5, '6. 잉여 자금 및 실적', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value', axisLabel: { formatter: yAxisFormatter }, scale: true },
        series: [
            { name: '순단기금융자산', type: 'bar', data: viewData.map(d => d['순단기금융자산']) },
            { name: '당기순이익', type: 'line', data: viewData.map(d => d['당기순이익']) }
        ]
    });

    // 7. 현금흐름 추이 및 기업 상태
    applyOption(6, '7. 현금흐름 3대 지표', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value', axisLabel: { formatter: yAxisFormatter }, scale: true },
        series: [
            { name: '영업활동CF', type: 'line', data: viewData.map(d => d['영업활동현금흐름']) },
            { name: '투자활동CF', type: 'line', data: viewData.map(d => d['투자활동현금흐름']) },
            { name: '재무활동CF', type: 'line', data: viewData.map(d => d['재무활동현금흐름']) }
        ]
    });

    // 8. ROE & PBR & ROIC
    applyOption(7, '8. 자본 효율성 (ROE, ROIC, PBR)', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: [
            { type: 'value', name: '수익성(%)', scale: true },
            { type: 'value', name: 'PBR(배)', splitLine: { show: false }, scale: true }
        ],
        series: [
            { name: 'ROE', type: 'line', data: viewData.map(d => round2(d['ROE'])) },
            { name: 'ROIC', type: 'line', data: viewData.map(d => round2(d['ROIC'])) },
            { name: 'PBR', type: 'line', yAxisIndex: 1, data: viewData.map(d => round2(d['PBR'])) }
        ]
    });

    // 9. 영업활동현금흐름 대비 재투자(CAPEX)
    applyOption(8, '9. 영업활동현금흐름 대비 재투자(CAPEX/OCF)', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: [
            { type: 'value', name: '금액(원)', axisLabel: { formatter: yAxisFormatter }, scale: true },
            { type: 'value', name: '비율(%)', scale: true, splitLine: { show: false } }
        ],
        series: [
            { name: 'CAPEX', type: 'bar', data: viewData.map(d => d['CAPEX']) },
            { name: 'CAPEX/OCF 비율', type: 'line', yAxisIndex: 1, data: viewData.map(d => round2(d['CAPEX_OCF_비율'])) }
        ]
    });

    // 10. PER 차트 (밴드 데이터 연동)
    if (globalChartData && globalChartData.band_data && globalChartData.band_data.length > 0) {
        let useAnnualBand = (currentMode === 'Annual' && globalChartData.annual_band_data && globalChartData.annual_band_data.length > 0);
        let bandData = useAnnualBand ? globalChartData.annual_band_data : globalChartData.band_data;
        window.currentBandData = bandData;

        // 툴바 표시
        let perToolbar = document.getElementById('perBandToolbar');
        let pbrToolbar = document.getElementById('pbrBandToolbar');
        let dyToolbar = document.getElementById('dyBandToolbar');
        if (perToolbar) perToolbar.style.display = 'flex';
        if (pbrToolbar) pbrToolbar.style.display = 'flex';
        if (dyToolbar) dyToolbar.style.display = 'flex';
        
        let bandXAxis = bandData.map(d => d.date || d.Year);
        let currentPrice = viewData.length > 0 && viewData[0]['주가'] ? viewData[0]['주가'].toLocaleString() : '-';
        let bandLabel = useAnnualBand ? '(연간/연말종가)' : '(TTM/주말종가)';
        
        const priceFormatter = (value) => {
            if (value == null || isNaN(value)) return '-';
            if (value >= 1000000) return parseFloat((value / 1000000).toFixed(2)) + '백만원';
            if (value >= 10000) return parseFloat((value / 10000).toFixed(2)) + '만원';
            return value.toLocaleString() + '원';
        };
        
        // 10. PER 차트 (밴드 데이터 연동, 우측 주가축 왜곡 방지를 위해 환산주가는 숨김 3축에 격리)
        // 극단적 이상치(ISC 4,526배, 두산테스나 634배 등 EPS 0원 수렴) 발생 시에만 선택적 스마트 캡 적용 (정상 기업 왜곡 0%)
        let pMax = (bandData.length > 0 && bandData[0]['PER_Max']) ? bandData[0]['PER_Max'] : 0;
        let p90 = (bandData.length > 0 && bandData[0]['PER_Plus1SD']) ? bandData[0]['PER_Plus1SD'] : 0;
        let perYAxisOpt = { type: 'value', name: 'PER(배)', scale: true };
        if (p90 > 0 && (pMax / p90 > 3.0) && pMax > 150) {
            perYAxisOpt.max = Math.max(150, Math.ceil(p90 * 1.5));
        }

        applyOption(9, `10. 주가수익비율 (PER) 밴드 ${bandLabel} (현재 주가: ${currentPrice}원)`, {
            xAxis: { type: 'category', data: bandXAxis },
            yAxis: [
                perYAxisOpt,
                { type: 'value', name: '주가(원)', scale: true, splitLine: { show: false }, axisLabel: { formatter: yAxisFormatter } },
                { type: 'value', show: false }
            ],
            series: [
                { name: '역사적 최고점', type: 'line', data: bandData.map(d => round2(d['PER_Max'])), lineStyle: { type: 'dashed', color: '#ff4d4f' }, symbol: 'none' },
                { name: '상위 10%', type: 'line', data: bandData.map(d => round2(d['PER_Plus1SD'])), lineStyle: { type: 'dashed', color: '#ffa39e' }, symbol: 'none' },
                { name: '10년 중앙값', type: 'line', data: bandData.map(d => round2(d['PER_Average'])), lineStyle: { color: '#e6a23c', width: 4 }, symbol: 'none' },
                { name: '하위 10%', type: 'line', data: bandData.map(d => round2(d['PER_Minus1SD'])), lineStyle: { type: 'dashed', color: '#91caff' }, symbol: 'none' },
                { name: '역사적 최저점', type: 'line', data: bandData.map(d => round2(d['PER_Min'])), lineStyle: { type: 'dashed', color: '#1890ff' }, symbol: 'none' },
                { name: 'PER', type: 'line', data: bandData.map(d => round2(d['PER'])), lineStyle: { color: '#ffffff', width: 2 }, itemStyle: { color: '#ffffff' }, areaStyle: { opacity: 0.1 } },
                { 
                    name: '주가', 
                    type: 'line', 
                    yAxisIndex: 1, 
                    data: bandData.map(d => d['price']), 
                    lineStyle: { color: '#00ff00', width: 2 }, 
                    symbol: 'none',
                    tooltip: { valueFormatter: priceFormatter }
                },
                { 
                    name: '상위 10% 환산주가', 
                    type: 'line', 
                    yAxisIndex: 2, 
                    data: bandData.map(d => d['정상화EPS'] ? Math.round(d['PER_Plus1SD'] * d['정상화EPS']) : null), 
                    lineStyle: { opacity: 0 }, 
                    itemStyle: { color: '#ffa39e' }, 
                    symbol: 'none',
                    showSymbol: false, 
                    tooltip: { valueFormatter: priceFormatter } 
                },
                { 
                    name: '하위 10% 환산주가', 
                    type: 'line', 
                    yAxisIndex: 2, 
                    data: bandData.map(d => d['정상화EPS'] ? Math.round(d['PER_Minus1SD'] * d['정상화EPS']) : null), 
                    lineStyle: { opacity: 0 }, 
                    itemStyle: { color: '#91caff' }, 
                    symbol: 'none',
                    showSymbol: false, 
                    tooltip: { valueFormatter: priceFormatter } 
                }
            ]
        });

        // 11. PBR 차트 (밴드 데이터 연동)
        applyOption(10, `11. 주가순자산비율 (PBR) 밴드 ${bandLabel} (현재 주가: ${currentPrice}원)`, {
            xAxis: { type: 'category', data: bandXAxis },
            yAxis: [
                { type: 'value', name: 'PBR(배)', scale: true },
                { type: 'value', name: '주가(원)', scale: true, splitLine: { show: false }, axisLabel: { formatter: yAxisFormatter } },
                { type: 'value', show: false }
            ],
            series: [
                { name: '역사적 최고점', type: 'line', data: bandData.map(d => round2(d['PBR_Max'])), lineStyle: { type: 'dashed', color: '#ff4d4f' }, symbol: 'none' },
                { name: '상위 10%', type: 'line', data: bandData.map(d => round2(d['PBR_Plus1SD'])), lineStyle: { type: 'dashed', color: '#ffa39e' }, symbol: 'none' },
                { name: '10년 중앙값', type: 'line', data: bandData.map(d => round2(d['PBR_Average'])), lineStyle: { color: '#e6a23c', width: 4 }, symbol: 'none' },
                { name: '하위 10%', type: 'line', data: bandData.map(d => round2(d['PBR_Minus1SD'])), lineStyle: { type: 'dashed', color: '#91caff' }, symbol: 'none' },
                { name: '역사적 최저점', type: 'line', data: bandData.map(d => round2(d['PBR_Min'])), lineStyle: { type: 'dashed', color: '#1890ff' }, symbol: 'none' },
                { name: 'PBR', type: 'line', data: bandData.map(d => round2(d['PBR'])), lineStyle: { color: '#ffffff', width: 2 }, itemStyle: { color: '#ffffff' }, areaStyle: { opacity: 0.1 } },

                { 
                    name: '주가', 
                    type: 'line', 
                    yAxisIndex: 1, 
                    data: bandData.map(d => d['price']), 
                    lineStyle: { color: '#00ff00', width: 2 }, 
                    symbol: 'none',
                    tooltip: { valueFormatter: priceFormatter }
                },
                { 
                    name: '상위 10% 환산주가', 
                    type: 'line', 
                    yAxisIndex: 1, 
                    data: bandData.map(d => d['BPS'] ? Math.round(d['PBR_Plus1SD'] * d['BPS']) : null), 
                    lineStyle: { opacity: 0 }, 
                    itemStyle: { color: '#ffa39e' }, 
                    showSymbol: false, 
                    tooltip: { valueFormatter: priceFormatter } 
                },
                { 
                    name: '하위 10% 환산주가', 
                    type: 'line', 
                    yAxisIndex: 1, 
                    data: bandData.map(d => d['BPS'] ? Math.round(d['PBR_Minus1SD'] * d['BPS']) : null), 
                    lineStyle: { opacity: 0 }, 
                    itemStyle: { color: '#91caff' }, 
                    showSymbol: false, 
                    tooltip: { valueFormatter: priceFormatter } 
                },
                { 
                    name: '현재 ROE', 
                    type: 'line', 
                    yAxisIndex: 2,
                    data: bandData.map(d => round2(d['Current_ROE'])), 
                    showSymbol: false, 
                    lineStyle: { opacity: 0 } 
                },
                { 
                    name: '10년 평균 ROE', 
                    type: 'line', 
                    yAxisIndex: 2,
                    data: bandData.map(d => round2(d['Median_ROE'])), 
                    showSymbol: false, 
                    lineStyle: { opacity: 0 } 
                }
            ]
        });

        // 12. 배당수익률 차트 (밴드 데이터 연동)
        applyOption(11, `12. 주가배당수익률 (Dividend Yield) 밴드 ${bandLabel} (현재 주가: ${currentPrice}원)`, {
            xAxis: { type: 'category', data: bandXAxis },
            yAxis: [
                { type: 'value', name: '배당수익률(%)', scale: true },
                { type: 'value', name: '주가(원)', scale: true, splitLine: { show: false }, axisLabel: { formatter: yAxisFormatter } },
                { type: 'value', show: false }
            ],
            series: [
                { name: '역사적 최고점', type: 'line', data: bandData.map(d => round2(d['DY_Max'])), lineStyle: { type: 'dashed', color: '#ff4d4f' }, symbol: 'none' },
                { name: '상위 10%', type: 'line', data: bandData.map(d => round2(d['DY_Plus1SD'])), lineStyle: { type: 'dashed', color: '#ffa39e' }, symbol: 'none' },
                { name: '10년 중앙값', type: 'line', data: bandData.map(d => round2(d['DY_Average'])), lineStyle: { color: '#e6a23c', width: 4 }, symbol: 'none' },
                { name: '하위 10%', type: 'line', data: bandData.map(d => round2(d['DY_Minus1SD'])), lineStyle: { type: 'dashed', color: '#91caff' }, symbol: 'none' },
                { name: '역사적 최저점', type: 'line', data: bandData.map(d => round2(d['DY_Min'])), lineStyle: { type: 'dashed', color: '#1890ff' }, symbol: 'none' },
                { name: '배당수익률', type: 'line', data: bandData.map(d => round2(d['배당수익률'])), lineStyle: { color: '#ffffff', width: 2 }, itemStyle: { color: '#ffffff' }, areaStyle: { opacity: 0.1 }, symbol: 'none' },
                { 
                    name: '주가', 
                    type: 'line', 
                    yAxisIndex: 1, 
                    data: bandData.map(d => d['price']), 
                    lineStyle: { color: '#00ff00', width: 2 }, 
                    symbol: 'none',
                    tooltip: { valueFormatter: priceFormatter }
                },
                { 
                    name: '상위 10% 환산주가 (안전마진)', 
                    type: 'line', 
                    yAxisIndex: 2, 
                    data: bandData.map(d => (d['수정DPS'] && d['DY_Plus1SD'] > 0) ? Math.round(d['수정DPS'] / (d['DY_Plus1SD'] / 100)) : null), 
                    lineStyle: { opacity: 0 }, 
                    itemStyle: { color: '#ffa39e' }, 
                    symbol: 'none',
                    showSymbol: false, 
                    tooltip: { valueFormatter: priceFormatter } 
                },
                { 
                    name: '하위 10% 환산주가 (저배당)', 
                    type: 'line', 
                    yAxisIndex: 2, 
                    data: bandData.map(d => (d['수정DPS'] && d['DY_Minus1SD'] > 0) ? Math.round(d['수정DPS'] / (d['DY_Minus1SD'] / 100)) : null), 
                    lineStyle: { opacity: 0 }, 
                    itemStyle: { color: '#91caff' }, 
                    symbol: 'none',
                    showSymbol: false, 
                    tooltip: { valueFormatter: priceFormatter } 
                }
            ]
        });
        
        // --- 동적 줌(Zoom) 시 밴드 재계산 및 기간 표시 연동 ---
        const updateBands = (chartIndex, key, titlePrefix) => {
            let chart = charts[chartIndex];
            if (!chart) return;
            setTimeout(() => {
                let opt = chart.getOption();
                let startIdx = 0;
                let endIdx = bandData.length - 1;
                
                if (opt.dataZoom && opt.dataZoom[0]) {
                    let startPercent = opt.dataZoom[0].start;
                    let endPercent = opt.dataZoom[0].end;
                    startIdx = Math.floor(bandData.length * startPercent / 100);
                    endIdx = Math.ceil(bandData.length * endPercent / 100) - 1;
                    if(startIdx < 0) startIdx = 0;
                    if(endIdx >= bandData.length) endIdx = bandData.length - 1;
                }
                
                let sliced = bandData.slice(startIdx, endIdx + 1);
                let allVals = sliced.map(d => d[key]).filter(v => v > 0);
                let vals = allVals.slice();

                // UI 기간 배지 및 입력란 동기화
                let firstDate = new Date(bandData[0].date || `${bandData[0].Year}-01-01`);
                let lastDate = new Date(bandData[bandData.length - 1].date || `${bandData[bandData.length - 1].Year}-12-31`);
                let totalMonths = Math.max(1, Math.round((lastDate - firstDate) / (1000 * 60 * 60 * 24 * 30.4375)));

                let sDate = new Date(bandData[startIdx].date || `${bandData[startIdx].Year}-01-01`);
                let eDate = new Date(bandData[endIdx].date || `${bandData[endIdx].Year}-12-31`);
                let curMonths = Math.max(1, Math.round((eDate - sDate) / (1000 * 60 * 60 * 24 * 30.4375)));
                let isFull = (startIdx === 0 && endIdx >= bandData.length - 1);
                
                let sStr = bandData[startIdx].date || bandData[startIdx].Year;
                let eStr = bandData[endIdx].date || bandData[endIdx].Year;
                
                updateBandPeriodUI(chartIndex, isFull ? totalMonths : curMonths, sStr, eStr, isFull);
                currentBandMonths[chartIndex] = isFull ? 'all' : curMonths;
                
                if (allVals.length > 0) {
                    vals.sort((a,b) => a - b);
                    let median = vals.length % 2 === 0 ? (vals[vals.length/2 - 1] + vals[vals.length/2]) / 2 : vals[Math.floor(vals.length/2)];
                    let p10 = vals[Math.floor(vals.length * 0.1)] || vals[0];
                    let p90 = vals[Math.floor(vals.length * 0.9)] || vals[vals.length - 1];
                    let max = vals[vals.length - 1];
                    let min = vals[0];
                    
                    let unit = key === '배당수익률' ? '%' : '배';
                    let targetP90 = d => (key === 'PER' ? (d['정상화EPS'] ? Math.round(p90 * d['정상화EPS']) : null) : (key === 'PBR' ? (d['BPS'] ? Math.round(p90 * d['BPS']) : null) : ((d['수정DPS'] && p90 > 0) ? Math.round(d['수정DPS'] / (p90 / 100)) : null)));
                    let targetP10 = d => (key === 'PER' ? (d['정상화EPS'] ? Math.round(p10 * d['정상화EPS']) : null) : (key === 'PBR' ? (d['BPS'] ? Math.round(p10 * d['BPS']) : null) : ((d['수정DPS'] && p10 > 0) ? Math.round(d['수정DPS'] / (p10 / 100)) : null)));

                    let yAxisUpdate = [];
                    if (key === 'PER') {
                        if (p90 > 0 && (max / p90 > 3.0) && max > 150) {
                            yAxisUpdate = [{ max: Math.max(150, Math.ceil(p90 * 1.5)) }];
                        } else {
                            yAxisUpdate = [{ max: null }];
                        }
                    }

                    chart.setOption({
                        title: { text: `${titlePrefix} ${bandLabel} (현재 주가: ${currentPrice}원, 확대구간 중앙값: ${round2(median)}${unit})`, left: 'center', top: 0, triggerEvent: true },
                        ...(yAxisUpdate.length > 0 ? { yAxis: yAxisUpdate } : {}),
                        series: [
                            { data: bandData.map(() => round2(max)) },
                            { data: bandData.map(() => round2(p90)) },
                            { data: bandData.map(() => round2(median)) },
                            { data: bandData.map(() => round2(p10)) },
                            { data: bandData.map(() => round2(min)) },
                            {}, // 실제 값(PER/PBR/배당수익률)
                            {}, // 주가
                            { data: bandData.map(targetP90) },
                            { data: bandData.map(targetP10) }
                        ]
                    });
                } else {
                    chart.setOption({
                        title: { text: `${titlePrefix} ${bandLabel} (현재 주가: ${currentPrice}원, 확대구간 중앙값: -)`, left: 'center', top: 0, triggerEvent: true }
                    });
                }

                // 슬라이더 조작 시 PER/PBR/배당수익률 전체 동기화
                if (syncBandPeriods && !isSyncingZoom) {
                    [9, 10, 11].forEach(targetIndex => {
                        if (targetIndex !== chartIndex) {
                            let targetChart = charts[targetIndex];
                            if (targetChart && opt.dataZoom && opt.dataZoom[0]) {
                                isSyncingZoom = true;
                                targetChart.setOption({
                                    dataZoom: [
                                        { type: 'inside', start: opt.dataZoom[0].start, end: opt.dataZoom[0].end },
                                        { type: 'slider', start: opt.dataZoom[0].start, end: opt.dataZoom[0].end }
                                    ]
                                });
                                let targetKey = targetIndex === 9 ? 'PER' : (targetIndex === 10 ? 'PBR' : '배당수익률');
                                let targetPrefix = targetIndex === 9 ? '10. 주가수익비율 (PER) 밴드' : (targetIndex === 10 ? '11. 주가순자산비율 (PBR) 밴드' : '12. 주가배당수익률 (Dividend Yield) 밴드');
                                updateBands(targetIndex, targetKey, targetPrefix);
                            }
                        }
                    });
                    setTimeout(() => { isSyncingZoom = false; }, 80);
                }
            }, 50);
        };

        window.updateBandChart = (chartIndex) => {
            if (chartIndex === 9) updateBands(9, 'PER', '10. 주가수익비율 (PER) 밴드');
            else if (chartIndex === 10) updateBands(10, 'PBR', '11. 주가순자산비율 (PBR) 밴드');
            else if (chartIndex === 11) updateBands(11, '배당수익률', '12. 주가배당수익률 (Dividend Yield) 밴드');
        };

        charts[9].off('dataZoom');
        charts[9].on('dataZoom', () => updateBands(9, 'PER', '10. 주가수익비율 (PER) 밴드'));
        charts[10].off('dataZoom');
        charts[10].on('dataZoom', () => updateBands(10, 'PBR', '11. 주가순자산비율 (PBR) 밴드'));
        charts[11].off('dataZoom');
        charts[11].on('dataZoom', () => updateBands(11, '배당수익률', '12. 주가배당수익률 (Dividend Yield) 밴드'));

        // 초기 기간 반영
        let initialPeriod = currentBandMonths[9] || 'all';
        setBandPeriod(9, initialPeriod, true);
        setBandPeriod(10, initialPeriod, true);
        setBandPeriod(11, initialPeriod, true);

    } else {
        // 과거 캐시 등 밴드 데이터가 없을 경우 Fallback
        let perToolbar = document.getElementById('perBandToolbar');
        let pbrToolbar = document.getElementById('pbrBandToolbar');
        let dyToolbar = document.getElementById('dyBandToolbar');
        if (perToolbar) perToolbar.style.display = 'none';
        if (pbrToolbar) pbrToolbar.style.display = 'none';
        if (dyToolbar) dyToolbar.style.display = 'none';

        applyOption(9, '10. 주가수익비율 (PER) 밴드', {
            xAxis: { type: 'category', data: xAxisData },
            yAxis: { type: 'value', name: 'PER(배)', scale: true },
            series: [
                { name: 'PER', type: 'line', data: viewData.map(d => round2(d['PER'])), areaStyle: { opacity: 0.2 } }
            ]
        });
        applyOption(10, '11. 주가순자산비율 (PBR) 밴드', {
            xAxis: { type: 'category', data: xAxisData },
            yAxis: { type: 'value', name: 'PBR(배)', scale: true },
            series: [
                { name: 'PBR', type: 'line', data: viewData.map(d => round2(d['PBR'])), areaStyle: { opacity: 0.2 } }
            ]
        });
        applyOption(11, '12. 주가배당수익률 (Dividend Yield) 밴드', {
            xAxis: { type: 'category', data: xAxisData },
            yAxis: { type: 'value', name: '배당수익률(%)', scale: true },
            series: [
                { name: '배당수익률', type: 'line', data: viewData.map(d => round2(d['배당수익률'])), areaStyle: { opacity: 0.2 } }
            ]
        });
    }
}
