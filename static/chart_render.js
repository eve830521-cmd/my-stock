let globalChartData = null;
let charts = [];
let currentMode = 'TTM'; // 'TTM' or 'Annual'

document.addEventListener("DOMContentLoaded", () => {
    // 11개 차트 초기화 (다크모드 테마 적용)
    for (let i = 1; i <= 11; i++) {
        let chartDom = document.getElementById('chart' + i);
        if (chartDom) {
            let chart = echarts.init(chartDom, 'dark');
            charts.push(chart);
        }
    }
    
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
            title: { text: title, left: 'center', top: 0 },
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

    // 9. 영업이익 & CAPEX
    applyOption(8, '9. 영업이익 대비 재투자(CAPEX)', {
        xAxis: { type: 'category', data: xAxisData },
        yAxis: { type: 'value', axisLabel: { formatter: yAxisFormatter }, scale: true },
        series: [
            { name: '영업이익', type: 'bar', data: viewData.map(d => d['영업이익']) },
            { name: 'CAPEX', type: 'line', data: viewData.map(d => d['CAPEX']) }
        ]
    });

    // 10. PER 차트 (밴드 데이터 연동)
    if (globalChartData && globalChartData.band_data && globalChartData.band_data.length > 0) {
        let useAnnualBand = (currentMode === 'Annual' && globalChartData.annual_band_data && globalChartData.annual_band_data.length > 0);
        let bandData = useAnnualBand ? globalChartData.annual_band_data : globalChartData.band_data;
        
        let bandXAxis = bandData.map(d => d.date || d.Year);
        let currentPrice = viewData.length > 0 && viewData[0]['주가'] ? viewData[0]['주가'].toLocaleString() : '-';
        let bandLabel = useAnnualBand ? '(연간/연말종가)' : '(TTM/주말종가)';
        
        applyOption(9, `10. 주가수익비율 (PER) 밴드 ${bandLabel} (현재 주가: ${currentPrice}원)`, {
            xAxis: { type: 'category', data: bandXAxis },
            yAxis: [
                { type: 'value', name: 'PER(배)', scale: true },
                { type: 'value', name: '주가(원)', scale: true, splitLine: { show: false }, axisLabel: { formatter: yAxisFormatter } }
            ],
            series: [
                { name: 'Max', type: 'line', data: bandData.map(d => round2(d['PER_Max'])), lineStyle: { type: 'dashed', color: '#ff4d4f' }, symbol: 'none' },
                { name: '+1SD', type: 'line', data: bandData.map(d => round2(d['PER_Plus1SD'])), lineStyle: { type: 'dashed', color: '#ffa39e' }, symbol: 'none' },
                { name: 'Average', type: 'line', data: bandData.map(d => round2(d['PER_Average'])), lineStyle: { color: '#e6a23c', width: 4 }, symbol: 'none' },
                { name: '-1SD', type: 'line', data: bandData.map(d => round2(d['PER_Minus1SD'])), lineStyle: { type: 'dashed', color: '#91caff' }, symbol: 'none' },
                { name: 'Min', type: 'line', data: bandData.map(d => round2(d['PER_Min'])), lineStyle: { type: 'dashed', color: '#1890ff' }, symbol: 'none' },
                { name: 'PER', type: 'line', data: bandData.map(d => round2(d['PER'])), lineStyle: { color: '#ffffff', width: 2 }, itemStyle: { color: '#ffffff' }, areaStyle: { opacity: 0.1 } },
                { name: '주가', type: 'line', yAxisIndex: 1, data: bandData.map(d => d['price']), lineStyle: { color: '#00ff00', width: 2 }, symbol: 'none' }
            ]
        });

        // 11. PBR 차트 (밴드 데이터 연동)
        applyOption(10, `11. 주가순자산비율 (PBR) 밴드 ${bandLabel} (현재 주가: ${currentPrice}원)`, {
            xAxis: { type: 'category', data: bandXAxis },
            yAxis: [
                { type: 'value', name: 'PBR(배)', scale: true },
                { type: 'value', name: '주가(원)', scale: true, splitLine: { show: false }, axisLabel: { formatter: yAxisFormatter } }
            ],
            series: [
                { name: 'Max', type: 'line', data: bandData.map(d => round2(d['PBR_Max'])), lineStyle: { type: 'dashed', color: '#ff4d4f' }, symbol: 'none' },
                { name: '+1SD', type: 'line', data: bandData.map(d => round2(d['PBR_Plus1SD'])), lineStyle: { type: 'dashed', color: '#ffa39e' }, symbol: 'none' },
                { name: 'Average', type: 'line', data: bandData.map(d => round2(d['PBR_Average'])), lineStyle: { color: '#e6a23c', width: 4 }, symbol: 'none' },
                { name: '-1SD', type: 'line', data: bandData.map(d => round2(d['PBR_Minus1SD'])), lineStyle: { type: 'dashed', color: '#91caff' }, symbol: 'none' },
                { name: 'Min', type: 'line', data: bandData.map(d => round2(d['PBR_Min'])), lineStyle: { type: 'dashed', color: '#1890ff' }, symbol: 'none' },
                { name: 'PBR', type: 'line', data: bandData.map(d => round2(d['PBR'])), lineStyle: { color: '#ffffff', width: 2 }, itemStyle: { color: '#ffffff' }, areaStyle: { opacity: 0.1 } },
                { name: '주가', type: 'line', yAxisIndex: 1, data: bandData.map(d => d['price']), lineStyle: { color: '#00ff00', width: 2 }, symbol: 'none' }
            ]
        });
        
        // --- 동적 줌(Zoom) 시 밴드 재계산 이벤트 연동 ---
        const updateBands = (chartIndex, key, titlePrefix) => {
            let chart = charts[chartIndex];
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
                let vals = sliced.map(d => d[key]).filter(v => v > 0);
                
                if (vals.length > 0) {
                    let mean = vals.reduce((a,b)=>a+b, 0) / vals.length;
                    let std = Math.sqrt(vals.map(x => Math.pow(x - mean, 2)).reduce((a,b)=>a+b, 0) / vals.length);
                    let max = Math.max(...vals);
                    let min = Math.min(...vals);
                    
                    chart.setOption({
                        title: { text: `${titlePrefix} ${bandLabel} (현재 주가: ${currentPrice}원, 확대구간 평균: ${round2(mean)}배)` },
                        series: [
                            { data: bandData.map(() => round2(max)) },
                            { data: bandData.map(() => round2(mean + std)) },
                            { data: bandData.map(() => round2(mean)) },
                            { data: bandData.map(() => round2(mean - std)) },
                            { data: bandData.map(() => round2(min)) },
                            {}, // 실제 값(PER/PBR) 라인은 그대로 둠
                            {}  // 주가 라인도 그대로 둠
                        ]
                    });
                }
            }, 50);
        };

        charts[9].off('dataZoom');
        charts[9].on('dataZoom', () => updateBands(9, 'PER', '10. 주가수익비율 (PER) 밴드'));
        charts[10].off('dataZoom');
        charts[10].on('dataZoom', () => updateBands(10, 'PBR', '11. 주가순자산비율 (PBR) 밴드'));

    } else {
        // 과거 캐시 등 밴드 데이터가 없을 경우 Fallback
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
    }
}
