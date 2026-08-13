let currentDcfParams = {};

function calculateCAGR(dataArray, key, years) {
    if (dataArray.length < 2) return null;
    const end = dataArray[dataArray.length - 1];
    const startIndex = Math.max(0, dataArray.length - 1 - years);
    const start = dataArray[startIndex];
    const actualYears = dataArray.length - 1 - startIndex;
    if (actualYears <= 0 || start[key] <= 0 || end[key] <= 0) return null;
    return (Math.pow(end[key] / start[key], 1 / actualYears) - 1) * 100;
}

function calculateMarginStats(dataArray, years) {
    if (dataArray.length === 0) return { max: 0, min: 0, avg: 0 };
    const startIndex = Math.max(0, dataArray.length - years);
    const slice = dataArray.slice(startIndex);
    let margins = slice.map(d => {
        if (d['매출액'] === 0) return NaN;
        return (d['영업이익'] / d['매출액']) * 100;
    }).filter(m => !isNaN(m));
    
    if (margins.length === 0) return { max: 0, min: 0, avg: 0 };
    let max = Math.max(...margins);
    let min = Math.min(...margins);
    let avg = margins.reduce((a, b) => a + b, 0) / margins.length;
    return { max, min, avg };
}

function getFcfBase(annualData) {
    if (annualData.length < 3) return (annualData[annualData.length-1].FCF || 0) / 100000000;
    const slice = annualData.slice(-5).map(d => (d.FCF || 0) / 100000000);
    if (slice.length < 3) return slice[slice.length-1];
    let max = Math.max(...slice);
    let min = Math.min(...slice);
    let sum = slice.reduce((a, b) => a + b, 0);
    return (sum - max - min) / (slice.length - 2);
}

function formatCurrencyDynamic(val) {
    if (val === null || val === undefined) return '-';
    return Math.round(val).toLocaleString();
}

let globalAnnualData = [];

function renderDcfTab(data) {
    const annualData = data.annual_data;
    globalAnnualData = annualData;
    if (!annualData || annualData.length === 0) return;
    
    // 연도별 요약 표 렌더링 (억원 단위)
    const tbody = document.querySelector('#annualTable tbody');
    tbody.innerHTML = '';
    annualData.forEach(d => {
        let tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${d.Year}</td>
            <td>${formatCurrencyDynamic(d['매출액'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['영업이익'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['이익률'])}%</td>
            <td>${formatCurrencyDynamic(d['NOPAT'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['당기순이익'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['당기순이익률'])}%</td>
            <td>${formatCurrencyDynamic(d['ROE'])}%</td>
            <td>${formatCurrencyDynamic(d['ROIC'])}%</td>
            <td>${formatCurrencyDynamic(d['배당금'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['영업활동현금흐름'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['CAPEX'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['FCF'] / 100000000)}</td>
            <td>${formatCurrencyDynamic(d['감가상각비'] / 100000000)}</td>
            <td>${(d['법인세율'] * 100).toFixed(1)}%</td>
        `;
        tbody.appendChild(tr);
    });
    
    const exportBtn = document.getElementById('exportDcfBtn');
    exportBtn.style.display = 'inline-block';
    exportBtn.onclick = exportDcfToCSV;

    const recentYear = annualData[annualData.length - 1];
    const baseYear = recentYear.Year;
    let marginStats = calculateMarginStats(annualData, 5);
    
    let currentPrice = recentYear['주가'] || 0;
    let shares = recentYear['유통주식수'] || 0;
    let netCash = ((recentYear['현금및현금성자산'] || 0) + (recentYear['단기금융자산'] || 0)) - (recentYear['단기금융부채'] || 0);
    let taxRate = recentYear['법인세율'] || 0.22;

    let p_margin = marginStats.max > 0 ? marginStats.max : 15;
    let n_margin = marginStats.avg > 0 ? marginStats.avg : 10;
    let b_margin = marginStats.min > 0 ? marginStats.min : 5;
    
    let html = `
        <div style="display:flex; justify-content:space-between; gap:20px;">
            <!-- 1. 최근 매출성장률 평균 (기간 수기입력) -->
            <div style="flex:1;">
                <h3 style="color:white;">1. 최근 매출성장률 평균</h3>
                <table class="excel-table">
                    <tr>
                        <td>기간 1 (최대 10)</td>
                        <td><input type="number" id="revYears1" class="excel-input" value="10"> 년</td>
                        <td id="cagr1" class="calc-value">-</td>
                    </tr>
                    <tr>
                        <td>기간 2</td>
                        <td><input type="number" id="revYears2" class="excel-input" value="5"> 년</td>
                        <td id="cagr2" class="calc-value">-</td>
                    </tr>
                    <tr class="excel-header-row"><th colspan="3">매출연평균 성장률 요약</th></tr>
                    <tr><td colspan="2">최대</td><td id="cagrMax" class="calc-value" style="color:#f59e0b;">-</td></tr>
                    <tr><td colspan="2">평균</td><td id="cagrAvg" class="calc-value">-</td></tr>
                    <tr><td colspan="2">최저</td><td id="cagrMin" class="calc-value" style="color:#ef4444;">-</td></tr>
                </table>
            </div>

            <!-- 2. 최근 5년 영업이익률 평균 -->
            <div style="flex:1;">
                <h3 style="color:white;">2. 최근 5년 영업이익률 평균</h3>
                <div style="margin-bottom:10px;">
                    <span style="color:white; margin-right:15px; font-weight:bold;">가치평가 기준 선택:</span>
                    <label style="color:white; cursor:pointer;"><input type="radio" name="baseMetric" value="NOPAT" checked> 영업이익(NOPAT)</label>
                    <label style="color:white; cursor:pointer; margin-left:15px;"><input type="radio" name="baseMetric" value="FCF"> 잉여현금흐름(FCF)</label>
                </div>
                <table class="excel-table">
                    <tr class="excel-header-row">
                        <th>최고</th><th>평균</th><th>최저</th><th>긍정</th><th>중립</th><th>부정</th>
                    </tr>
                    <tr>
                        <td class="calc-value" style="text-align:center;">${marginStats.max.toFixed(2)}%</td>
                        <td class="calc-value" style="text-align:center;">${marginStats.avg.toFixed(2)}%</td>
                        <td class="calc-value" style="text-align:center;">${marginStats.min.toFixed(2)}%</td>
                        <td style="text-align:center;"><input type="number" id="scenMarginP" class="excel-input" value="${p_margin.toFixed(2)}">%</td>
                        <td style="text-align:center;"><input type="number" id="scenMarginN" class="excel-input" value="${n_margin.toFixed(2)}">%</td>
                        <td style="text-align:center;"><input type="number" id="scenMarginB" class="excel-input" value="${b_margin.toFixed(2)}">%</td>
                    </tr>
                </table>
                <p style="color:#94a3b8; font-size:0.85rem;">* FCF 선택 시 '긍정/중립/부정' 이익률 입력값은 무시되고, N+1년부터 FCF 기준금액에 매출성장률이 곱해집니다.</p>
            </div>
        </div>

        <!-- 3. 기타 내재가치 변수 -->
        <h3 style="color:white;">3. 기타 내재가치 변수</h3>
        <table class="excel-table">
            <tr class="excel-header-row">
                <th>할인율 (%)</th>
                <th>영구성장률 (%)</th>
                <th>현재 주가 (원)</th>
                <th>유통주식수 (수기입력, 0=자동)</th>
            </tr>
            <tr>
                <td style="text-align:center;"><input type="number" id="discountRate" class="excel-input" value="10" step="0.1">%</td>
                <td style="text-align:center;"><input type="number" id="terminalGrowth" class="excel-input" value="2" step="0.1">%</td>
                <td style="text-align:center;"><input type="text" id="currentPrice" class="excel-input" style="width: 120px; text-align: right;" value="${Math.round(currentPrice).toLocaleString()}" oninput="let v = this.value.replace(/[^0-9]/g, ''); this.value = v ? Number(v).toLocaleString() : '';"></td>
                <td style="text-align:center;">
                    <input type="text" id="manualShares" class="excel-input" style="width: 140px; text-align: right;" 
                        value="${Math.ceil(shares).toLocaleString()}" 
                        oninput="let v = this.value.replace(/[^0-9]/g, ''); this.value = v ? Number(v).toLocaleString() : '';">
                </td>
            </tr>
        </table>
        
        <!-- 시나리오별 DCF 테이블 렌더링 컨테이너 -->
        <div id="dcfScenarioTables"></div>

        <!-- 6. 최종 기댓값 및 결과 표 -->
        <h3 style="color:white;">6. 내재가치 결과</h3>
        <table class="excel-table" id="finalResultTable">
            <tr class="excel-header-row">
                <th>시나리오</th>
                <th>확률</th>
                <th>가치 (억원)</th>
                <th>기댓값 (억원)</th>
            </tr>
            <tr>
                <td>긍정</td>
                <td><input type="number" id="probP" class="excel-input" value="30">%</td>
                <td id="valP" class="calc-value">0</td>
                <td id="expP" class="calc-value">0</td>
            </tr>
            <tr>
                <td>중립</td>
                <td><input type="number" id="probN" class="excel-input" value="40">%</td>
                <td id="valN" class="calc-value">0</td>
                <td id="expN" class="calc-value">0</td>
            </tr>
            <tr>
                <td>부정</td>
                <td><input type="number" id="probB" class="excel-input" value="30">%</td>
                <td id="valB" class="calc-value">0</td>
                <td id="expB" class="calc-value">0</td>
            </tr>
            <tr style="background-color:#334155;">
                <td colspan="2" style="text-align:center; font-weight:bold;">합계</td>
                <td></td>
                <td id="expTotal" class="calc-value" style="color:#10b981; font-size:1.1rem;">0</td>
            </tr>
            <tr>
                <td colspan="3" style="text-align:right;">순현금(단기금융-단기부채)</td>
                <td id="netCashDisplay" class="calc-value">${formatCurrencyDynamic(netCash / 100000000)}</td>
            </tr>
            <tr>
                <td colspan="3" style="text-align:right;">최종 적정주가 (원)</td>
                <td id="finalTargetPrice" class="calc-value" style="color:#f59e0b; font-size:1.2rem;">0</td>
            </tr>
        </table>
        
        <!-- 최종 결과물 시각화 카드 (기대수익률) -->
        <div id="dcfResultCard" class="result-card">
            <div class="result-item">
                <span>현재 주가</span>
                <h2 id="cardCurrentPrice">${formatCurrencyDynamic(currentPrice)} 원</h2>
            </div>
            <div class="result-item">
                <span>최종 적정 주가</span>
                <h2 id="cardTargetPrice">-</h2>
            </div>
            <div class="result-item">
                <span>예상 연평균 수익률</span>
                <h2 id="cardExpectedReturn" class="highlight">-</h2>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- S-RIM 가치평가 시작 -->
        <!-- ============================================== -->
        <hr style="border-color:#334155; margin:40px 0;">
        <h2 style="color:white; text-align:center;">S-RIM (사경인 회계사 잔여이익모델)</h2>
        
        <div style="display:flex; justify-content:space-between; gap:20px; margin-top:20px;">
            <!-- 과거 ROE 추이 -->
            <div style="flex:1;">
                <h3 style="color:white;">1. 과거 지배주주 ROE 추이</h3>
                <table class="excel-table">
                    <tr class="excel-header-row">
                        <th>${baseYear - 2}년</th>
                        <th>${baseYear - 1}년</th>
                        <th>${baseYear}년(최근)</th>
                        <th style="background-color:#3b82f6;">3년 평균</th>
                    </tr>
                    <tr>
                        <td style="text-align:center;">${(annualData.length >= 3 && annualData[annualData.length-3]['ROE']) ? annualData[annualData.length-3]['ROE'].toFixed(2) : 0}%</td>
                        <td style="text-align:center;">${(annualData.length >= 2 && annualData[annualData.length-2]['ROE']) ? annualData[annualData.length-2]['ROE'].toFixed(2) : 0}%</td>
                        <td style="text-align:center;">${(annualData.length >= 1 && annualData[annualData.length-1]['ROE']) ? annualData[annualData.length-1]['ROE'].toFixed(2) : 0}%</td>
                        <td style="text-align:center; font-weight:bold;">${(() => {
                            let count = 0, sum = 0;
                            for (let i=1; i<=3; i++) {
                                if (annualData.length >= i && annualData[annualData.length-i]['ROE']) {
                                    sum += annualData[annualData.length-i]['ROE'];
                                    count++;
                                }
                            }
                            return count > 0 ? (sum/count).toFixed(2) : 0;
                        })()}%</td>
                    </tr>
                </table>
            </div>
            
            <!-- S-RIM 입력 변수 -->
            <div style="flex:1;">
                <h3 style="color:white;">2. S-RIM 입력 변수</h3>
                <table class="excel-table">
                    <tr>
                        <td style="background-color:#1e293b;">예상 ROE (%)</td>
                        <td><input type="number" id="srimExpectedRoe" class="excel-input" value="${(() => {
                            let count = 0, sum = 0;
                            for (let i=1; i<=3; i++) {
                                if (annualData.length >= i && annualData[annualData.length-i]['ROE']) {
                                    sum += annualData[annualData.length-i]['ROE'];
                                    count++;
                                }
                            }
                            return count > 0 ? (sum/count).toFixed(2) : 0;
                        })()}" step="0.1" style="color:#f59e0b; font-weight:bold; width:80px; text-align:center;"> %</td>
                    </tr>
                    <tr>
                        <td style="background-color:#1e293b;">요구수익률 (%)</td>
                        <td style="font-weight:bold; padding-left:10px;">10.0% (고정)</td>
                    </tr>
                    <tr>
                        <td style="background-color:#1e293b;">지배주주자본 (억원)</td>
                        <td style="padding-left:10px;" id="srimEquityBase">${formatCurrencyDynamic((recentYear['자본총계'] || 0) / 100000000)}</td>
                    </tr>
                    <tr>
                        <td style="background-color:#1e293b;">유통주식수</td>
                        <td style="padding-left:10px;" id="srimSharesDisplay">${Math.ceil(shares).toLocaleString()}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <!-- S-RIM 적정주가 결과 -->
        <h3 style="color:white; margin-top:20px;">3. S-RIM 시나리오별 적정주가 산출 (초과이익 지속계수 w 기준)</h3>
        <table class="excel-table" id="srimResultTable">
            <tr class="excel-header-row">
                <th>시나리오</th>
                <th>초과이익 지속계수 (w)</th>
                <th>적정 기업가치 (억원)</th>
                <th>S-RIM 적정주가 (원)</th>
            </tr>
            <tr>
                <td style="font-weight:bold;">초과이익 영구 지속</td>
                <td style="text-align:center;">1.00</td>
                <td id="srimVal_1" class="calc-value">0</td>
                <td id="srimPrice_1" class="calc-value" style="color:#f59e0b; font-weight:bold; font-size:1.1rem;">0</td>
            </tr>
            <tr>
                <td style="font-weight:bold;">초과이익 10%씩 감소</td>
                <td style="text-align:center;">0.90</td>
                <td id="srimVal_09" class="calc-value">0</td>
                <td id="srimPrice_09" class="calc-value" style="color:#10b981; font-weight:bold; font-size:1.1rem;">0</td>
            </tr>
            <tr>
                <td style="font-weight:bold;">초과이익 20%씩 감소</td>
                <td style="text-align:center;">0.80</td>
                <td id="srimVal_08" class="calc-value">0</td>
                <td id="srimPrice_08" class="calc-value" style="color:#ef4444; font-weight:bold; font-size:1.1rem;">0</td>
            </tr>
        </table>
        <p style="color:#94a3b8; font-size:0.85rem; margin-top:5px;">* 계산식: 기업가치 = 자본 + 자본 × (예상ROE - 요구수익률) × w / (1 + 요구수익률 - w)</p>
    `;
    
    document.getElementById('dcfFormArea').innerHTML = html;
    
    // 시나리오 렌더링
    renderScenarioTables(baseYear);
    
    // 이벤트 바인딩
    const inputs = document.querySelectorAll('.excel-input, input[name="baseMetric"]');
    inputs.forEach(input => {
        input.addEventListener('change', () => {
            updateCagrs();
            calculateDCF(recentYear, taxRate, netCash);
            calculateSRIM(recentYear);
        });
        
        // manualShares oninput 시 S-RIM sharesDisplay도 업데이트
        if (input.id === 'manualShares') {
            input.addEventListener('input', () => {
                let v = input.value.replace(/[^0-9]/g, '');
                document.getElementById('srimSharesDisplay').textContent = v ? Number(v).toLocaleString() : '0';
            });
        }
    });
    
    updateCagrs();
    calculateDCF(recentYear, taxRate, netCash);
    calculateSRIM(recentYear);
}

function calculateSRIM(recentYear) {
    const expectedRoe = parseFloat(document.getElementById('srimExpectedRoe').value) / 100;
    const requiredReturn = 0.10; // 10% 고정
    const equityBase = (recentYear['자본총계'] || 0) / 100000000;
    
    const sharesRaw = document.getElementById('manualShares').value.replace(/,/g, '');
    const shares = parseFloat(sharesRaw) || recentYear['유통주식수'];
    
    // w = 1.0, 0.9, 0.8
    const scenarios = [
        { id: '1', w: 1.0 },
        { id: '09', w: 0.9 },
        { id: '08', w: 0.8 }
    ];
    
    scenarios.forEach(scen => {
        // 기업가치 = 자본 + 자본 * (ROE - COE) * w / (1 + COE - w)
        let residualIncome = equityBase * (expectedRoe - requiredReturn);
        let intrinsicValue = equityBase + (residualIncome * scen.w) / (1 + requiredReturn - scen.w);
        
        // 적정주가 = (적정가치(억원) * 100,000,000) / 유통주식수
        let targetPrice = (intrinsicValue * 100000000) / shares;
        
        document.getElementById(`srimVal_${scen.id}`).textContent = formatCurrencyDynamic(intrinsicValue);
        document.getElementById(`srimPrice_${scen.id}`).textContent = formatCurrencyDynamic(targetPrice);
    });
}

function updateCagrs() {
    let y1 = parseInt(document.getElementById('revYears1').value) || 10;
    let y2 = parseInt(document.getElementById('revYears2').value) || 5;
    
    let cagr1 = calculateCAGR(globalAnnualData, '매출액', y1);
    let cagr2 = calculateCAGR(globalAnnualData, '매출액', y2);
    
    document.getElementById('cagr1').textContent = cagr1 !== null ? cagr1.toFixed(2) + '%' : '-';
    document.getElementById('cagr2').textContent = cagr2 !== null ? cagr2.toFixed(2) + '%' : '-';
    
    if (cagr1 !== null && cagr2 !== null) {
        let max = Math.max(cagr1, cagr2);
        let min = Math.min(cagr1, cagr2);
        let avg = (cagr1 + cagr2) / 2;
        document.getElementById('cagrMax').textContent = max.toFixed(2) + '%';
        document.getElementById('cagrAvg').textContent = avg.toFixed(2) + '%';
        document.getElementById('cagrMin').textContent = min.toFixed(2) + '%';
    }
}

function renderScenarioTables(baseYear) {
    const scenarios = [
        { id: 'P', title: '5.1 긍정 시나리오', defaultGrowths: [10, 10, 10, 10, 10] },
        { id: 'N', title: '5.2 중립 시나리오', defaultGrowths: [5, 5, 5, 5, 5] },
        { id: 'B', title: '5.3 부정 시나리오', defaultGrowths: [2, 2, 2, 2, 2] }
    ];
    
    let container = document.getElementById('dcfScenarioTables');
    let html = '';
    
    scenarios.forEach(scen => {
        let thead = `<tr><th>연도</th><th style="background-color:#eab308; color:black;">${baseYear}년 (N)</th>`;
        let revGrowthRow = `<tr><td>예상 매출성장률(%)</td><td>-</td>`;
        let revRow = `<tr><td>예상 매출액</td><td id="revBase_${scen.id}" class="calc-value">0</td>`;
        let nopatRow = `<tr><td id="nopatLabel_${scen.id}">세후 영업이익</td><td id="nopatBase_${scen.id}" class="calc-value">-</td>`;
        let discFactorRow = `<tr><td>할인 계수</td><td class="calc-value">-</td>`;
        let discNopatRow = `<tr><td>할인 현금흐름</td><td class="calc-value">-</td>`;
        
        for (let i = 1; i <= 5; i++) {
            thead += `<th>${baseYear + i}년</th>`;
            revGrowthRow += `<td><input type="number" id="g_${scen.id}_${i}" class="excel-input" value="${scen.defaultGrowths[i-1]}"></td>`;
            revRow += `<td id="rev_${scen.id}_${i}" class="calc-value">0</td>`;
            nopatRow += `<td id="nopat_${scen.id}_${i}" class="calc-value">0</td>`;
            discFactorRow += `<td id="df_${scen.id}_${i}" class="calc-value">0</td>`;
            discNopatRow += `<td id="dn_${scen.id}_${i}" class="calc-value">0</td>`;
        }
        
        thead += `<th>영구가치</th><th>합계</th></tr>`;
        revGrowthRow += `<td></td><td></td></tr>`;
        revRow += `<td></td><td></td></tr>`;
        nopatRow += `<td id="tv_${scen.id}" class="calc-value">0</td><td id="tv_sum_${scen.id}" class="calc-value">0</td></tr>`;
        discFactorRow += `<td id="df_tv_${scen.id}" class="calc-value">0</td><td></td></tr>`;
        discNopatRow += `<td id="dn_tv_${scen.id}" class="calc-value">0</td><td id="total_${scen.id}" class="calc-value" style="color:#3b82f6;">0</td></tr>`;
        
        html += `
            <h3 style="color:white; margin-top:20px;">${scen.title} (단위: 억원)</h3>
            <table class="excel-table scenario-table" id="table_${scen.id}">
                <thead>${thead}</thead>
                <tbody>${revGrowthRow}${revRow}${nopatRow}${discFactorRow}${discNopatRow}</tbody>
            </table>
        `;
    });
    
    container.innerHTML = html;
}

function calculateDCF(recentYear, taxRate, netCash) {
    const dr = parseFloat(document.getElementById('discountRate').value) / 100;
    const tg = parseFloat(document.getElementById('terminalGrowth').value) / 100;
    const sharesRaw = document.getElementById('manualShares').value.replace(/,/g, '');
    const shares = parseFloat(sharesRaw) || recentYear['유통주식수'];
    const currentPrice = parseFloat(document.getElementById('currentPrice').value.replace(/,/g, '')) || 0;
    
    const baseMetric = document.querySelector('input[name="baseMetric"]:checked').value; // 'NOPAT' or 'FCF'
    
    const marginP = parseFloat(document.getElementById('scenMarginP').value) / 100;
    const marginN = parseFloat(document.getElementById('scenMarginN').value) / 100;
    const marginB = parseFloat(document.getElementById('scenMarginB').value) / 100;
    
    const scenarios = [
        { id: 'P', margin: marginP, prob: parseFloat(document.getElementById('probP').value) / 100 },
        { id: 'N', margin: marginN, prob: parseFloat(document.getElementById('probN').value) / 100 },
        { id: 'B', margin: marginB, prob: parseFloat(document.getElementById('probB').value) / 100 }
    ];
    
    let totalExpectedValue = 0;
    let baseRev = (recentYear['매출액'] || 0) / 100000000; // 억원 단위
    let fcfBase = getFcfBase(globalAnnualData);
    let nopatBase = (recentYear['NOPAT'] || 0) / 100000000;
    
    scenarios.forEach(scen => {
        let currentRev = baseRev;
        let sumPV = 0;
        let cf5 = 0;
        
        let labelDom = document.getElementById(`nopatLabel_${scen.id}`);
        let baseValDom = document.getElementById(`nopatBase_${scen.id}`);
        document.getElementById(`revBase_${scen.id}`).textContent = formatCurrencyDynamic(baseRev);
        
        if (baseMetric === 'FCF') {
            labelDom.textContent = '잉여현금흐름(FCF)';
            baseValDom.textContent = formatCurrencyDynamic(fcfBase);
        } else {
            labelDom.textContent = '세후 영업이익';
            baseValDom.textContent = formatCurrencyDynamic(nopatBase);
        }
        
        let currentCf = baseMetric === 'FCF' ? fcfBase : 0;
        
        for (let i = 1; i <= 5; i++) {
            let g = parseFloat(document.getElementById(`g_${scen.id}_${i}`).value) / 100;
            currentRev = currentRev * (1 + g);
            
            let cf = 0;
            if (baseMetric === 'FCF') {
                currentCf = currentCf * (1 + g);
                cf = currentCf;
            } else {
                cf = currentRev * scen.margin * (1 - taxRate);
            }
            
            let df = Math.pow((1 + dr), i);
            let pv = cf / df;
            
            document.getElementById(`rev_${scen.id}_${i}`).textContent = formatCurrencyDynamic(currentRev);
            document.getElementById(`nopat_${scen.id}_${i}`).textContent = formatCurrencyDynamic(cf);
            document.getElementById(`df_${scen.id}_${i}`).textContent = df.toFixed(3);
            document.getElementById(`dn_${scen.id}_${i}`).textContent = formatCurrencyDynamic(pv);
            
            sumPV += pv;
            if (i === 5) cf5 = cf;
        }
        
        // 영구가치 (Terminal Value) 계산 (N+5년 CF 기준)
        let tv = (cf5 * (1 + tg)) / (dr - tg);
        let df_tv = Math.pow((1 + dr), 5);
        let pv_tv = tv / df_tv;
        
        document.getElementById(`tv_${scen.id}`).textContent = formatCurrencyDynamic(tv);
        document.getElementById(`df_tv_${scen.id}`).textContent = df_tv.toFixed(3);
        document.getElementById(`dn_tv_${scen.id}`).textContent = formatCurrencyDynamic(pv_tv);
        
        let totalVal = sumPV + pv_tv;
        document.getElementById(`tv_sum_${scen.id}`).textContent = formatCurrencyDynamic(tv + (cf5*5)); // 단순 표시
        document.getElementById(`total_${scen.id}`).textContent = formatCurrencyDynamic(totalVal);
        
        // 내재가치 요약 표 업데이트
        document.getElementById(`val${scen.id}`).textContent = formatCurrencyDynamic(totalVal);
        let expectedVal = totalVal * scen.prob;
        document.getElementById(`exp${scen.id}`).textContent = formatCurrencyDynamic(expectedVal);
        
        totalExpectedValue += expectedVal;
    });
    
    document.getElementById('expTotal').textContent = formatCurrencyDynamic(totalExpectedValue);
    
    let netCashH = netCash / 100000000;
    let targetMarketCapH = totalExpectedValue + netCashH;
    let targetPrice = (targetMarketCapH * 100000000) / shares; 
    
    document.getElementById('finalTargetPrice').textContent = formatCurrencyDynamic(targetPrice);
    document.getElementById('cardTargetPrice').textContent = formatCurrencyDynamic(targetPrice) + ' 원';
    document.getElementById('cardCurrentPrice').textContent = formatCurrencyDynamic(currentPrice) + ' 원';
    
    let expectedReturn = Math.pow((targetPrice / currentPrice), 1/5) - 1;
    let retDom = document.getElementById('cardExpectedReturn');
    retDom.textContent = (expectedReturn * 100).toFixed(2) + '%';
    if (expectedReturn < 0) {
        retDom.style.color = '#ef4444';
    } else {
        retDom.style.color = '#10b981';
    }
}

// 엑셀 다운로드 (DCF 기대수익률 시뮬레이션 테이블 묶음)
function exportDcfToCSV() {
    let csv = [];
    // 시나리오 3개 테이블
    ['P', 'N', 'B'].forEach(id => {
        let table = document.getElementById(`table_${id}`);
        if(table) {
            let title = table.previousElementSibling.innerText;
            csv.push(title);
            for (let i = 0; i < table.rows.length; i++) {
                let row = [], cols = table.rows[i].querySelectorAll("td, th");
                for (let j = 0; j < cols.length; j++) {
                    let input = cols[j].querySelector('input');
                    let val = input ? input.value : cols[j].innerText;
                    row.push('"' + val.replace(/"/g, '""') + '"');
                }
                csv.push(row.join(","));
            }
            csv.push(""); // 빈 줄
        }
    });

    // 6. 내재가치 결과 테이블
    let resTable = document.getElementById("finalResultTable");
    if(resTable) {
        csv.push("6. 내재가치 결과");
        for (let i = 0; i < resTable.rows.length; i++) {
            let row = [], cols = resTable.rows[i].querySelectorAll("td, th");
            for (let j = 0; j < cols.length; j++) {
                let input = cols[j].querySelector('input');
                let val = input ? input.value : cols[j].innerText;
                row.push('"' + val.replace(/"/g, '""') + '"');
            }
            csv.push(row.join(","));
        }
    }

    let csvContent = "\uFEFF" + csv.join("\n");
    let blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    let link = document.createElement("a");
    let url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", "DCF_시나리오_분석결과.csv");
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
