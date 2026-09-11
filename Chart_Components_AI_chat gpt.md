응. 이건 꽤 진지하게 만든 문서고, 전체 구조는 괜찮아. 다만 내가 보기에는 “투자 아이디어를 설명하는 문서”로서는 상당히 좋지만, 그대로 ChatGPT나 Claude에게 넘겨서 정확한 투자 대시보드를 구현시키는 설계 명세서로 쓰기에는 몇 군데 치명적인 논리 충돌이 있다.

내 평가는 대략 이렇다.

항목	평가	점수
투자철학의 일관성	좋음	8.5/10
한국 경기민감주에 대한 지표 구성	좋음	8/10
차트 1~11의 전체 흐름	매우 좋음	9/10
재무지표 정의의 엄밀성	일부 문제	6.5/10
통계적 valuation band	보완 필요	6/10
Point-in-time / 백테스트 엄밀성	핵심 수정 필요	5.5/10
ChatGPT가 이해·구현하기 좋은가	좋지만 명세화 필요	8/10
Claude가 이해·구현하기 좋은가	좋지만 명세화 필요	8/10

결론부터 말하면 아이디어 자체를 버릴 필요는 전혀 없고, 오히려 골격은 꽤 잘 짜여 있다. 하지만 3~4개의 핵심 로직은 반드시 고쳐야 한다.

가장 중요한 것부터 보자.

1. 현재 주식수로 과거 EPS/BPS를 다시 계산하는 부분 — 이게 가장 큰 문제

문서에서는 이렇게 정의했다.

과거 10년 전체 EPS/BPS를 현재 발행주식수로 소급 계산하여 CB·유상증자 등의 희석을 모두 반영한다.

아이디어가 뭔지는 아주 잘 알겠어.

예를 들어 과거에

100억 이익 / 100만 주 = EPS 10,000원

이었다가 이후 CB와 유상증자로 200만 주가 됐다면,

과거의 EPS 10,000원을 그대로 보고 "과거 PER 5배였다"고 판단하면 현재 주주 입장에서는 착시가 있다는 논리잖아.

그래서

100억 / 현재 200만 주 = 5,000원

으로 과거도 다시 계산하겠다는 것.

현재 투자자의 관점에서 과거 실적을 현재 share base로 환산해 보는 보조지표로는 꽤 흥미로운 아이디어다.

그런데 이걸 historical valuation backtest에 넣는 순간 문제가 생긴다.

2018년 투자자는 2022년에 CB가 발행될지 몰랐는데, 2018년 EPS 계산에 2022년 희석을 집어넣게 되니까 future information이 과거 valuation에 들어간다.

IAS 33에서도 정식 EPS는 해당 기간의 가중평균 유통주식수를 분모로 사용한다.

그러니까 파일의

"Look-ahead bias를 제거했다"

와

"current outstanding shares를 과거 전체에 소급 적용한다"

는 동시에 성립할 수 없다.

이건 내가 이 문서에서 가장 먼저 형에게 지적할 부분이다.

해결책은 오히려 간단해.

두 개를 분리하면 된다.

Point-in-Time EPS/BPS
→ 당시 실제 주식수 사용
→ 실제 매매신호/백테스트/PER·PBR band용

Current-Share-Equivalent EPS/BPS
→ 현재 주식수로 historical data 재작성
→ 희석 정도를 보여주는 참고용 chart

이렇게 하면 오히려 원래 의도까지 살릴 수 있다.

2. Normalized EPS라고 부르는 식도 조금 이상하다

문서의 식은

Operating Profit × (1-Tax Rate) × Controlling Interest Ratio / Current Shares

이다.

엄밀하게 말하면 이건 EPS보다는 세후 영업이익 기반의 custom operating earnings per share에 가깝다.

정식 EPS의 numerator는 기본적으로 모회사 보통주 주주에게 귀속되는 profit이다.

여기서 영업이익을 출발점으로 해버리면 문제가 하나 생긴다.

회사 A와 B가 영업이익 1,000억으로 동일한데

A: 무차입
B: 부채 2조, 이자비용 700억

이라면 이 방식에서는 둘의 normalized EPS가 거의 동일하게 나올 수 있다.

하지만 equity holder에게 귀속될 수 있는 earnings power는 전혀 다르지.

그래서 이 식을 유지하려면 명칭을

Normalized Operating EPS

정도로 바꾸는 편이 맞다.

아니면 PER band에 정말 사용할 목적이라면

Normalized Parent NI / Point-in-Time Diluted Shares

쪽으로 가는 게 개념적으로 더 깨끗하다.

영업이익 기반 지표를 쓰고 싶다면 NOPAT → invested capital → ROIC와 연결시키는 쪽이 오히려 재무적으로 자연스럽다.

3. PBR 아이디어 자체는 좋은데, "-1SD = 절대적 저평가"는 성립하지 않는다

이 문서에서 가장 중요한 투자 논리가 PBR band다.

이건 경기민감주 대시보드라는 목적에는 상당히 합리적이라고 생각한다.

반도체, 화학, 철강처럼 EPS가

100 → 30 → 3 → -20 → 10 → 100

이렇게 움직이면 저점에서 PER가 폭발하거나 음수가 돼버리니까 PBR을 보는 이유도 충분히 이해된다.

다만

10년 PBR 평균 - 1SD = intrinsic undervaluation

처럼 받아들이면 안 된다.

왜냐하면 PBR 자체가 ROE, 성장률, payout, cost of equity 등에 의해 달라지기 때문이다. Damodaran 역시 P/B의 핵심 결정요인으로 ROE를 들고 있고, cost of equity와 성장률 등의 영향을 받는다고 설명한다.

예를 들어 회사 ROE가 구조적으로

15% → 7%

로 내려갔다면,

10년 전 PBR 1.0과 지금 PBR 1.0은 같은 valuation이라고 볼 수 없다.

그래서 내가 만들었다면 PBR chart에 한 줄을 더 넣겠다.

PBR percentile + ROE regime

즉,

현재 PBR: 0.62배
10Y percentile: 8%
10Y median: 1.05배
현재 normalized ROE: 8.2%
10Y normalized ROE: 11.4%

이렇게.

그러면

"싸긴 한데 기업 자체가 예전보다 나빠져서 싼 것인지"

를 구분할 수 있다.

4. 평균 ±1SD도 생각보다 "statistically robust"한 방법은 아니다

여기 문서에서 표현을 좀 과하게 썼다.

PER >120 제외, PBR >10 제외하고 Mean ±1SD를 쓰는 방식이다.

문제는 threshold가 상당히 arbitrary하다는 것이다.

왜 PER 120인가?

왜 PBR 10인가?

119는 정상이고 121은 outlier인가?

그리고 PER/PBR distribution 자체가 정규분포라고 보기도 어렵다.

그래서 AI한테 맡기면 더 나은 방법은 오히려

Median / percentile / MAD

같은 robust statistic을 같이 계산하게 하는 거다.

특히 투자자가 직관적으로 보기에는

현재 PBR = 역사적 6 percentile

이

-1.37 SD

보다 해석하기 쉽다.

내가 한다면 SD band를 없애지는 않고,

Mean ±1SD + 10/25/50/75/90 percentile

을 같이 계산하게 한다.

그리고 EPS ≤ 0이면 PER는 그냥 N/A 처리하는 편이 낫다. 마이너스 PER나 near-zero EPS에서 나온 80배, 120배 같은 숫자 자체가 경제적 의미가 거의 없다.

5. DART의 look-ahead 처리 방향은 아주 좋다. 다만 구현 방식이 틀렸다

이건 형이 상당히 중요한 문제를 제대로 알고 만든 부분이다.

파일에서

Q1이 3월31일 끝났더라도 5월15일 이후 가격과 매칭한다.

고 되어 있다.

철학은 정확하다.

그런데 5월15일을 hard coding해서는 안 된다.

DART의 일반적인 분·반기보고서 제출기한은 45일이고 일부 경우 60일 예외도 있다.

무엇보다 회사가 5월8일에 실제 공시했다면 투자자는 5월9일에 이미 정보를 알고 있다.

따라서 AI에게는

report_period_end

가 아니라

dart_receipt_datetime

을 가져오도록 시켜야 한다.

그리고 더 엄밀하게는

공시시각 < 장마감 → 그날 또는 다음 거래일 적용
공시시각 > 장마감 → 다음 거래일 적용

같은 information_available_timestamp 개념을 만들어야 한다.

그렇게 해야 정말로 point-in-time valuation이 된다.

그래서 이 문서의 "100% authentic"라는 표현은 현재 상태에서는 빼는 게 맞고, 실제 DART 공시시각을 사용하면 그때 상당히 근접해진다.

6. Chart 1~9 자체는 구성이 상당히 좋다

여기는 내가 높은 점수를 주는 이유다.

흐름이

사업 성장성
→ margin
→ cash generation
→ balance sheet
→ ROE/ROA
→ dilution
→ dividend
→ share count
→ CAPEX
→ valuation

순서다.

즉 단순히

"PER 싸네 → 사자"

가 아니라

살아남을 기업인가 → 자본을 잘 굴리는가 → 주주가치를 훼손하지 않는가 → 지금 싼가

라는 순서라서 dashboard UX 관점에서도 상당히 논리적이다.

다만 설명 문구 몇 개는 과장됐다.

OP margin이 유지된다고 moat가 증명되는 것도 아니고 bankruptcy가 불가능해지는 것도 아니다.
FCF가 양수라고 흑자도산이 방지되는 것도 아니다.
배당이 downside를 제한한다고 보장할 수도 없다.

이런 건 각각

"evidence of pricing power",
"cash-generation quality",
"shareholder-return support"

정도로 표현하는 게 정확하다.

특히 재무건전성은 debt/equity 하나만 쓰기보다는

Net Debt / EBITDA
Interest Coverage
Cash / Short-term Debt

중 적어도 하나 정도는 추가하는 게 경기저점 생존력 판정에 훨씬 유용하다.

7. CAPEX / Operating Profit도 약간 손볼 필요가 있다

OP가 1,000 → 100 → -50으로 움직이는 경기민감주에서

CAPEX / OP

는 30% → 300% → 의미불명

이 되어버린다.

그래서 차트 자체를 없앨 필요는 없지만

CAPEX / Depreciation
CAPEX / Sales
CAPEX / OCF

도 같이 보는 게 좋다.

특히 유지보수 CAPEX와 성장 CAPEX를 구별할 수 있으면 가장 좋지만, DART 숫자만으로 완벽하게 자동 분류하는 것은 상당히 어렵다.

8. S-RIM은 아이디어만 있고 "구현 명세"가 없다

S-RIM을 쓰겠다는 방향은 Residual Income Valuation 개념상 자연스럽다. Residual income은 기본적으로 book value와 ROE - cost of equity의 관계에서 equity value를 평가한다.

그런데 현재 문서에는

Cost of Equity를 어떻게 정할지,
ROE를 몇 년 평균으로 할지,
일회성 ROE를 제거할지,
초과이익 지속계수를 어떻게 할지,
terminal assumption은 무엇인지

가 없다.

사람은 "대충 이런 뜻이구나" 하고 넘어가지만 ChatGPT나 Claude에게 코드를 맡길 경우 이 부분에서 모델이 알아서 가정을 만들어버릴 가능성이 크다.

이게 AI 구현 명세서 관점에서는 아주 중요하다.

그래서 ChatGPT와 Claude에 적합하냐?

둘 다 충분히 잘 읽는다.

Markdown 구조도 좋고 Phase 1 → 2 → 3 구조도 명확해서 모델이 전체 목적을 파악하기 쉽다.

다만 현재 문서는 Architecture/Rationale document이지 정확한 software specification은 아니다.

ChatGPT 쪽 최신 공식 가이드도 반복 설명을 줄이고, 규칙을 한 번씩 명확하게 정의하며, tool description과 instruction을 간결하고 정확하게 유지하는 것을 권한다.

Claude 역시 복잡한 instruction/context/input을 구분할 때 XML처럼 명시적인 구조를 사용하면 모호성을 줄일 수 있다고 공식적으로 안내한다.

즉 모델 차이보다는 문서 명세의 정확성이 훨씬 큰 변수다.

현재 상태에서 Claude에 넣든 ChatGPT에 넣든 아마 예쁜 코드는 만들어낼 거다. 문제는 둘 다 지금 문서의 모순까지 충실하게 구현할 수 있다는 거야.

그래서 내가 형한테 답한다면 이렇게 말할 것 같아.

“전체 차트 구성 논리와 경기민감주에 PBR/TTM을 중심으로 접근하는 구조는 상당히 합리적이다. 다만 현재 발행주식수로 과거 EPS/BPS를 소급하는 방식과 point-in-time backtest가 충돌하고, normalized EPS 정의와 PBR ±1SD 통계 처리도 수정이 필요하다. 이 세 부분만 그대로 구현하면 대시보드는 그럴듯해 보여도 과거 매수·매도 신호가 왜곡될 수 있다. ChatGPT/Claude 구현용 문서로는 충분히 좋은 베이스지만, 데이터 정의·공시 반영시점·결측/음수 처리·outlier 규칙·S-RIM parameter를 명시한 별도의 Calculation Specification이 하나 더 필요하다.”

특히 현재주식수 소급 문제는 꼭 알려줘. 나머지는 개선사항에 가깝지만 이건 현재 문서가 주장하는 "look-ahead bias 제거"와 정면으로 모순되는 부분이라, 퀀트적인 관점에서는 꽤 중요한 오류야.