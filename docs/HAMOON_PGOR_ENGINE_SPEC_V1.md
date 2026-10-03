# Hamoon — PGOR Engine Specification v1

> وضعیت: Technical Specification v1  
> مبنا: سند «ماشین توانمندسازی هامون» + `HAMOON_AI_ARCHITECTURE_BASELINE.md` + `HAMOON_TECHNICAL_ARCHITECTURE_V1.md` + `HAMOON_DATA_MODEL_V1.md`  
> اصل: **PGOR Engine یک موتور محاسباتی قطعی، نسخه‌بندی‌شده و قابل بازتولید است؛ LLM مجاز به حدس‌زدن P/G/O/R/E نیست.**

---

# 1. مرزبندی Source vs Technical Policy

این سند دو نوع قاعده را صریحاً از هم جدا می‌کند:

## 1.1 Source-backed Rules
مواردی که مستقیماً در سند Hamoon تعریف شده‌اند:

- چهار متغیر P/G/O/R
- ساختار Variable → Dimension → Indicator
- اندازه‌گیری Indicatorها در بازه 0..100
- Normalization به 0..1 با Min-Max
- Aggregation میانگین برای ساخت متغیرهای اصلی
- تابع پایه E
- شرط α + β + γ = 1
- نقش R به‌عنوان ضریب تعدیل‌کننده
- E bands
- آستانه تقریبی استقلال E≈0.7
- سه منبع داده: خوداظهاری، ارزیابی کارشناسی، داده بیرونی
- امکان کالیبراسیون ضرایب در آینده
- ثابت بودن ضرایب در فاز پایلوت و بازتنظیم در فاز توسعه

## 1.2 Technical Policies v1
مواردی که سند علمی عدد یا رفتار اجرایی دقیق برای آن‌ها تعیین نکرده و در این Spec به‌عنوان تصمیم فنی V1 تعریف می‌شوند:

- رفتار با Missing Value
- رفتار با Conflict
- Activation Rule برای Formula Version
- Data Completeness
- Snapshot Status
- Rounding / Precision
- Idempotency / reproducibility
- Engine error behavior
- mapping categorical UI → 0..100

این موارد باید در آینده در صورت تصمیم علمی/محصولی جدید، Versioned تغییر کنند؛ نه silently.

---

# 2. Engine Responsibilities

PGOR Engine فقط مسئول این زنجیره است:

```text
Accepted Indicator Observations
→ Normalization
→ Dimension Scores
→ P / G / O / R
→ E
→ Bottleneck
→ Band / Threshold Interpretation
→ Versioned PGOR Snapshot
```

PGOR Engine مسئول موارد زیر نیست:

- Diagnosis
- Prescription
- Prediction
- Provider Matching
- Outcome causality
- AI explanation generation
- correction of source data

---

# 3. Inputs

ورودی رسمی Engine:

```text
assessment_id
pgor_definition_version_id
scoring_version_id
formula_version_id
accepted_indicator_observations[]
calculation_context
```

هر Observation باید حداقل:

```text
indicator_definition_id
raw_score_0_100
source_id
effective_at
status
version
```

داشته باشد.

---

# 4. Accepted Input Rule

فقط Observationهایی که در زمان Calculation برای Assessment پذیرفته‌شده‌اند وارد محاسبه می‌شوند.

```text
Accepted Observation Set
≠
All Collected Observations
```

اگر چند Source برای یک Indicator وجود داشته باشد، Engine خودش Source Arbitration انجام نمی‌دهد.

Source Resolution باید قبل از Calculation انجام شده باشد و خروجی آن به شکل Accepted Observation Set به Engine برسد.

---

# 5. PGOR Definition v1

## 5.1 P — Participation

### انگیزه
- willingness_to_change
- hope_for_future

### مسئولیت‌پذیری
- follow_up
- commitment_fulfillment

### تعامل
- institutional_engagement
- social_participation

### حضور در برنامه‌ها
- training_participation
- session_participation
- development_activity_participation

---

## 5.2 G — Growth Capacity

### سرمایه انسانی
- education
- skill

### تجربه
- work_experience
- production_experience

### قابلیت یادگیری
- trainability
- adaptability

### سلامت عملکردی
- physical_function
- cognitive_function

---

## 5.3 O — Opportunity

### بازار
- demand_access
- employment_opportunity

### زیرساخت
- transportation_access
- internet_access

### دسترسی
- service_access
- capital_access

### شبکه اقتصادی
- economic_connections
- value_chain_access

---

## 5.4 R — Resilience

ابعاد/شاخص‌های تعریف‌شده در سند:

- income_stability
- social_support
- family_health_stability
- crisis_coping_capacity
- income_diversity

---

# 6. Raw Score

سند PGOR برای Indicatorها بازه زیر را تعریف می‌کند:

```text
0 <= raw_score <= 100
```

Engine باید مقدار خارج از این بازه را Reject کند.

---

# 7. Categorical UI Mapping

UI می‌تواند از Label انسانی استفاده کند، مانند:

```text
خیلی کم
کم
متوسط
بالا
خیلی بالا
```

اما سند Hamoon mapping عددی این دسته‌ها را تعیین نکرده است.

بنابراین V1:

> هیچ mapping عددی در PGOR Engine hard-code نمی‌شود.

Mapping باید از:

```text
SCORING_SCALE_VERSION
```

خوانده شود.

مثال مفهومی:

```text
label
→ scoring scale version
→ raw_score_0_100
```

تا قبل از تصویب Mapping، Engine فقط Raw Score معتبر 0..100 را محاسبه می‌کند.

---

# 8. Normalization

فرمول Source-backed:

```text
Xn = (X - Xmin) / (Xmax - Xmin)
```

برای Scale استاندارد 0..100:

```text
Xmin = 0
Xmax = 100
```

در نتیجه:

```text
normalized = raw_score / 100
```

Constraint:

```text
0 <= normalized <= 1
```

---

# 9. Precision Policy v1

تصمیم فنی:

- محاسبات داخلی با Decimal precision انجام شوند.
- در میانه Pipeline rounding انجام نشود.
- Snapshot مقدار کامل محاسباتی را نگه دارد.
- UI می‌تواند مقدار نمایشی Rounded تولید کند.

پیشنهاد Logical Precision:

```text
internal: at least 6 decimal places
display: product/UI policy
```

---

# 10. Dimension Aggregation

ساختار Source-backed:

```text
Variable
→ Dimensions
→ Indicators
```

V1:

```text
dimension_score =
mean(normalized accepted indicators in that dimension)
```

مثال:

```text
Motivation =
(willingness_to_change + hope_for_future) / 2
```

---

# 11. Variable Aggregation

سند برای P مثال می‌زند:

```text
P = (P1 + P2 + P3 + P4) / 4
```

و همین روش را برای G/O/R بیان می‌کند.

بنابراین V1:

```text
P = mean(P dimensions)
G = mean(G dimensions)
O = mean(O dimensions)
R = mean(R dimensions)
```

برای R که پنج بُعد تعریف شده‌اند:

```text
R =
(
 income_stability
 + social_support
 + family_health_stability
 + crisis_coping_capacity
 + income_diversity
) / 5
```

هیچ Weight داخلی برای Dimensionها در V1 تعریف نمی‌شود مگر در Definition Version آینده به‌صورت صریح تصویب شود.

---

# 12. Base Empowerment Formula

تابع Source-backed:

```text
E = (α P^3 + β G^2 + γ O)(0.5 + 0.5 R)
```

با:

```text
0 <= P,G,O,R <= 1
α + β + γ = 1
```

و:

```text
0 <= E <= 1
```

---

# 13. Coefficient Policy

سند مقدار عددی α، β و γ را مشخص نکرده است.

بنابراین:

> PGOR Engine نباید برای α/β/γ مقدار پیش‌فرض اختراع کند.

هر `PGOR_FORMULA_VERSION` برای Active شدن باید دارای:

```text
alpha
beta
gamma
approval
effective_from
version
```

باشد.

Validation:

```text
alpha >= 0
beta >= 0
gamma >= 0
abs((alpha + beta + gamma) - 1) <= configured_tolerance
```

تا زمانی که ضرایب رسمی تصویب نشده‌اند، Formula Version نباید Production-Active شود.

---

# 14. Pilot vs Calibration

Source-backed:

- در فاز پایلوت ضرایب ثابت‌اند.
- در فاز توسعه ضرایب بازتنظیم می‌شوند.
- مدل در آینده می‌تواند ضرایب ملی/استانی/منطقه‌ای و زمان‌مند داشته باشد.

V1 Implementation:

```text
FormulaVersion
- scope_type
- scope_id?
- valid_from
- valid_to?
- alpha
- beta
- gamma
```

ولی Engine v1 فقط یک Formula Version صریح را در هر Calculation مصرف می‌کند.

هیچ coefficient learning آنلاین داخل PGOR Engine انجام نمی‌شود.

---

# 15. Resilience Multiplier

Source-backed:

```text
M_R = 0.5 + 0.5R
```

پس:

```text
R = 0 → multiplier = 0.5
R = 1 → multiplier = 1
```

R وارد جمع Growth Engine نمی‌شود؛ نقش آن تعدیل‌کنندگی است.

---

# 16. Bottleneck

Product/Architecture Rule:

```text
bottleneck = min(P, G, O, R)
```

PGOR Snapshot باید مقدار و Variable bottleneck را ذخیره کند.

در Tie:

```text
bottleneck_variables = all variables with same minimum within tolerance
```

تا Engine بدون قاعده علمی اضافی یکی را تصادفی انتخاب نکند.

---

# 17. E Bands

Source-backed:

```text
0.0 <= E < 0.2  → SEVERE_CRISIS
0.2 <= E < 0.4  → VULNERABLE
0.4 <= E < 0.7  → SUPPORTED_EMPOWERMENT
0.7 <= E <= 1.0 → ECONOMIC_SOCIAL_INDEPENDENCE
```

آستانه:

```text
E* ≈ 0.7
```

در Implementation:

```text
independence_threshold = 0.7
```

در Formula/Policy Version ذخیره شود تا قابل Audit باشد.

---

# 18. P Threshold Interpretation

Source-backed:

```text
P < 0.3       → VERY_HIGH_RISK
0.3 <= P <= 0.6 → MEDIUM
P > 0.6       → DESIRABLE
```

برای Boundary handling در V1:

```text
P < 0.3
0.3 <= P <= 0.6
P > 0.6
```

همان متن سند حفظ می‌شود.

---

# 19. R Threshold Interpretation

Source-backed:

```text
R < 0.4       → FRAGILE
0.4 <= R <= 0.7 → ACCEPTABLE
R > 0.7       → STABLE
```

برای G و O در سند Threshold مشابهی تعریف نشده است.

> V1 نباید برای G/O band اختراع کند.

---

# 20. Missing Value Policy v1

سند علمی رفتار محاسباتی Missing Indicator را تعیین نکرده است.

تصمیم فنی محافظه‌کارانه V1:

## 20.1 Missing ≠ Zero

```text
MISSING
```

هرگز به شکل:

```text
0
```

تفسیر نمی‌شود.

---

## 20.2 Official Snapshot

برای `COMPLETED / OFFICIAL PGOR SNAPSHOT`:

تمام Indicatorهایی که در Definition Version با:

```text
required_for_complete_assessment = true
```

علامت خورده‌اند باید Accepted Observation داشته باشند.

در غیر این صورت:

```text
CALCULATION_BLOCKED_MISSING_REQUIRED_DATA
```

---

## 20.3 Draft Preview

سیستم می‌تواند Preview موقت تولید کند، اما:

- official snapshot نیست
- در Timeline به‌عنوان PGOR رسمی ذخیره نمی‌شود
- downstream Diagnosis رسمی از آن استفاده نمی‌کند
- باید completeness را صریح نمایش دهد

---

# 21. Data Completeness

Technical metric، نه بخشی از فرمول PGOR:

```text
completeness_ratio =
accepted_required_indicators /
total_required_indicators
```

Range:

```text
0..1
```

این مقدار:

- در E ضرب نمی‌شود
- score را دستکاری نمی‌کند
- فقط کیفیت/آمادگی Calculation را نشان می‌دهد

---

# 22. Conflict Policy v1

PGOR Engine Conflict Resolver نیست.

## حالت A — Accepted Value هنوز مشخص است

اگر Indicator چند Observation متعارض دارد ولی Current Accepted Observation مشخص است:

```text
use accepted observation
+
data_quality_flag = HAS_DISPUTE
```

## حالت B — Accepted Value مشخص نیست

اگر Required Indicator unresolved dispute دارد و هیچ Current Accepted Observation وجود ندارد:

```text
block official calculation
```

Error:

```text
CALCULATION_BLOCKED_UNRESOLVED_REQUIRED_CONFLICT
```

AI اجازه ندارد Conflict را خودکار حل کند.

---

# 23. Source Weighting

سند سه Source را تعریف می‌کند، اما وزن عددی متفاوت برای آن‌ها تعیین نکرده است.

پس V1:

> Source Type هیچ ضریب خودکاری در PGOR Score ندارد.

```text
HOUSEHOLD_DECLARATION
EXPERT_ASSESSMENT
EXTERNAL_DATA
```

پس از Source Resolution، مقدار پذیرفته‌شده وارد محاسبه می‌شود.

اگر در آینده Source Reliability مدل شود، باید در Policy/Calibration جداگانه و Versioned تعریف شود.

---

# 24. Data Quality Flags

PGOR Snapshot می‌تواند Flags داشته باشد:

```text
HAS_DISPUTE
HAS_RECENT_CORRECTION
HAS_STALE_SOURCE
HAS_LOW_EVIDENCE
PARTIAL_PREVIEW
NONE
```

این Flags مقدار P/G/O/R/E را در V1 تغییر نمی‌دهند.

---

# 25. PGOR Snapshot Status

```text
DRAFT_PREVIEW
OFFICIAL
SUPERSEDED
INVALIDATED
```

`OFFICIAL` فقط وقتی مجاز است که:

- required data complete باشد
- Formula Version active/approved باشد
- Definition Version valid باشد
- Scoring Version valid باشد
- no blocking conflict وجود داشته باشد

---

# 26. Reproducibility Contract

برای هر Official Snapshot باید ذخیره شود:

```text
assessment_id
definition_version_id
formula_version_id
scoring_version_id
engine_version
indicator_observation_ids[]
normalized_input_values[]
alpha
beta
gamma
input_fingerprint
calculated_at
```

شرط:

> Calculation با همان Inputs و Versions باید همان خروجی را تولید کند.

---

# 27. Input Fingerprint

پیشنهاد Technical:

Canonical serialize:

```text
indicator_id
observation_version
raw_score
normalized_score
definition_version
scoring_version
formula_version
```

مرتب‌سازی deterministic و سپس Hash.

هدف:

- detect accidental mutation
- reproducibility
- audit
- test comparison

---

# 28. Idempotency

اگر Engine با:

```text
same assessment
same accepted input set
same definition version
same scoring version
same formula version
same engine version
```

اجرا شود، باید خروجی Logical یکسان بدهد.

می‌توان Snapshot قبلی را reuse کرد اگر fingerprint یکسان است.

---

# 29. Calculation Pipeline

```text
1. Load Assessment
2. Load PGOR Definition Version
3. Resolve Accepted Observation Set
4. Validate Required Indicators
5. Validate Conflicts
6. Validate Raw Scores 0..100
7. Normalize Indicators
8. Aggregate Dimensions
9. Aggregate P/G/O/R
10. Load & validate Formula Version
11. Calculate Growth Engine
12. Apply Resilience Multiplier
13. Calculate E
14. Determine Bottleneck
15. Determine E Band
16. Compute Completeness
17. Attach Data Quality Flags
18. Generate Input Fingerprint
19. Persist Snapshot
20. Emit PGORSnapshotCalculated
```

---

# 30. Pseudocode

```text
function calculatePGOR(input):

  assert input.definitionVersion.isValid
  assert input.scoringVersion.isValid
  assert input.formulaVersion.isApproved

  observations = acceptedObservations(input.assessment)

  validateRequiredIndicators(observations)
  validateBlockingConflicts(observations)

  normalized = {}

  for observation in observations:
      assert 0 <= observation.rawScore <= 100
      normalized[indicator] =
          normalize(observation.rawScore, 0, 100)

  dimensions = aggregateDimensions(normalized)

  P = mean(dimensions.P)
  G = mean(dimensions.G)
  O = mean(dimensions.O)
  R = mean(dimensions.R)

  assert approximatelyEqual(
      alpha + beta + gamma,
      1
  )

  growth =
      alpha * pow(P, 3)
      + beta * pow(G, 2)
      + gamma * O

  resilienceMultiplier =
      0.5 + 0.5 * R

  E =
      growth * resilienceMultiplier

  bottlenecks =
      minVariables(P, G, O, R)

  return versionedSnapshot(...)
```

---

# 31. Engine Output Schema

```text
PGORCalculationResult
{
  assessment_id,
  pgor_definition_version,
  scoring_version,
  formula_version,
  engine_version,

  P,
  G,
  O,
  R,
  E,

  bottleneck_variables[],
  e_band,

  completeness_ratio,
  data_quality_flags[],

  input_fingerprint,
  calculated_at
}
```

---

# 32. Error Codes

```text
INVALID_RAW_SCORE
INVALID_NORMALIZED_SCORE
MISSING_REQUIRED_INDICATOR
UNRESOLVED_REQUIRED_CONFLICT
INVALID_DEFINITION_VERSION
INVALID_SCORING_VERSION
INVALID_FORMULA_VERSION
COEFFICIENT_SUM_INVALID
COEFFICIENT_OUT_OF_RANGE
EMPTY_DIMENSION
SNAPSHOT_REPRODUCIBILITY_FAILURE
```

Error باید structured باشد، نه متن آزاد.

---

# 33. Engine Versioning

```text
engine_version
definition_version
scoring_version
formula_version
```

چهار Version مستقل‌اند.

مثال:

```text
engine = 1.0.0
definition = pgor-v1
scoring = scale-v1
formula = formula-v1
```

تغییر هر یک می‌تواند Snapshot جدید ایجاد کند.

---

# 34. Formula Activation Rule

Formula Version فقط وقتی Active می‌شود که:

- α/β/γ مقدار صریح داشته باشند
- جمع آن‌ها برابر 1 باشد
- approval ثبت شده باشد
- effective_from مشخص باشد
- تست‌های Engine پاس شده باشند

هیچ fallback coefficient وجود ندارد.

---

# 35. Calibration Boundary

Calibration Engine و PGOR Engine جدا هستند.

```text
PGOR Engine
= calculate with approved parameters

Calibration Engine
= propose new parameters from evidence
```

Calibration حق تغییر مستقیم Formula Version فعال را ندارد.

چرخه:

```text
Historical Data
→ Calibration Candidate
→ Offline Evaluation
→ Review
→ Approval
→ New Formula Version
→ Controlled Activation
```

---

# 36. AI Boundary

AI می‌تواند:

- توضیح PGOR بدهد
- bottleneck را شرح دهد
- روند را تفسیر کند
- anomaly را flag کند
- evidence gap را نشان دهد

اما AI نمی‌تواند:

- raw score را حدس بزند
- missing را صفر کند
- accepted value را بی‌اجازه عوض کند
- coefficient production را خودکار تغییر دهد
- PGOR/E را خارج از Engine تولید کند

---

# 37. Temporal Rule

هر Official Snapshot به زمان Assessment مربوط است.

در Historical Reconstruction:

```text
Observation effective_at
+
Accepted State at T
+
Definition Version at T
+
Formula Version at T
→ PGOR Snapshot at T
```

استفاده از Current data برای بازنویسی Snapshot تاریخی ممنوع است.

---

# 38. Reassessment Rule

Reassessment Snapshot باید مستقل باشد.

```text
Assessment T1 → Snapshot S1
Assessment T2 → Snapshot S2
```

Trend:

```text
ΔP = P2 - P1
ΔG = G2 - G1
ΔO = O2 - O1
ΔR = R2 - R1
ΔE = E2 - E1
```

Trend Data Derived است و Source Snapshotها باید حفظ شوند.

---

# 39. Outcome Compatibility

Outcome Engine باید فقط Snapshotهای رسمی pre/post را مصرف کند.

```text
Official Snapshot Before
+
Intervention
+
Provider Result
+
Official Snapshot After
→ Hamoon Outcome Analysis
```

Draft Preview برای Outcome رسمی قابل استفاده نیست.

---

# 40. Threshold Versioning

E bands، P thresholds و R thresholds باید در Policy/Definition Version قابل Trace باشند.

حتی اگر در v1 ثابت‌اند، نباید فقط در Frontend hard-code شوند.

---

# 41. Unit Test Vectors — Source Rules

## 41.1 Normalization

```text
raw = 0   → normalized = 0
raw = 50  → normalized = 0.5
raw = 100 → normalized = 1
```

---

## 41.2 Resilience Multiplier

```text
R = 0   → multiplier = 0.5
R = 0.5 → multiplier = 0.75
R = 1   → multiplier = 1
```

---

## 41.3 Formula Boundary

برای هر α/β/γ معتبر:

```text
P=0,G=0,O=0 → E=0
```

اگر:

```text
P=1,G=1,O=1,R=1
and α+β+γ=1
```

آنگاه:

```text
E=1
```

---

# 42. Unit Test Fixture — Non-Production Coefficients

برای تست نرم‌افزاری فقط، نه برای مدل علمی Production:

```text
α = 1/3
β = 1/3
γ = 1/3
```

این ضرایب صرفاً fixture تست‌اند و نباید به‌عنوان ضرایب Hamoon تلقی شوند.

Test:

```text
P=0.5
G=0.5
O=0.5
R=0.5

E = 0.21875
```

Test دوم:

```text
P=0.8
G=0.6
O=0.4
R=0.5

E = 0.318
```

---

# 43. Dimension Aggregation Tests

مثال:

```text
Motivation:
willingness_to_change = 0.6
hope_for_future = 0.8

Motivation Score = 0.7
```

P Example:

```text
motivation = 0.7
responsibility = 0.6
interaction = 0.5
program_participation = 0.8

P = 0.65
```

---

# 44. Missing Tests

## Required missing

```text
required indicator missing
→ official calculation blocked
```

## Partial preview

```text
missing non-final input set
→ preview allowed
→ status = DRAFT_PREVIEW
→ not usable by official diagnosis
```

---

# 45. Conflict Tests

## Accepted exists

```text
external = employed
household = unemployed
accepted = unemployed

→ use unemployed score
→ flag HAS_DISPUTE if dispute still open
```

## No accepted value

```text
required indicator
+ unresolved conflict
+ no accepted observation

→ block official snapshot
```

---

# 46. Reproducibility Test

Given same:

- accepted observation IDs + versions
- definition version
- scoring version
- formula version
- engine version

expect:

```text
same P
same G
same O
same R
same E
same fingerprint
```

---

# 47. Snapshot Immutability

Official Snapshot پس از ایجاد نباید mutate شود.

اگر:

- data corrected
- formula changed
- definition changed

Snapshot جدید ساخته می‌شود و Snapshot قبلی:

```text
SUPERSEDED
```

می‌شود، اما حذف نمی‌شود.

---

# 48. Performance Requirement v1

PGOR Calculation باید Pure/Deterministic باشد و وابستگی مستقیم به LLM یا Remote AI Call نداشته باشد.

Architecture:

```text
Application
→ PGOR Engine
→ local deterministic calculation
→ Snapshot
```

AI بعداً Snapshot را مصرف می‌کند.

---

# 49. Observability

Metrics:

```text
pgor_calculation_count
pgor_calculation_latency
pgor_calculation_failure_count
pgor_missing_required_count
pgor_conflict_block_count
pgor_snapshot_reuse_count
pgor_reproducibility_failure_count
```

Dimensions:

```text
engine_version
definition_version
formula_version
assessment_type
```

PII نباید وارد metric labels شود.

---

# 50. Security

Engine باید Household PII را فقط به اندازه نیاز دریافت کند.

برای Calculation، معمولاً لازم نیست:

- نام
- کد ملی
- آدرس

وارد Core PGOR Function شوند.

Input اصلی Engine باید IDها و indicator scores/version refs باشد.

---

# 51. Explainability Contract

PGOR Engine باید توضیح محاسباتی تولید کند، نه توضیح مولد.

مثال:

```text
P = mean(P dimension scores)
G = mean(G dimension scores)
O = mean(O dimension scores)
R = mean(R dimension scores)

E = ...
formula_version = ...
```

لایه AI می‌تواند بعداً توضیح انسانی بسازد، ولی باید بر همین Trace تکیه کند.

---

# 52. API-Level Calculation Contract

نمونه Command مفهومی:

```text
CalculatePGOR {
  assessment_id,
  expected_assessment_version,
  formula_version_id
}
```

Response:

```text
PGORCalculationResult
```

Client حق ارسال P/G/O/R/E محاسبه‌شده به‌عنوان Source of Truth ندارد.

---

# 53. Event

پس از Official Calculation:

```text
PGORSnapshotCalculated
```

Payload حداقلی:

```text
snapshot_id
household_id
assessment_id
P
G
O
R
E
bottleneck_variables
formula_version
definition_version
engine_version
calculated_at
```

---

# 54. Non-Goals v1

در PGOR Engine v1 انجام نمی‌دهیم:

- online learning
- automatic coefficient tuning
- source reliability weighting
- ML imputation
- causal inference
- prediction
- simulation
- prescription
- provider matching
- LLM scoring

این‌ها Engineهای جدا هستند.

---

# 55. Open Decisions

موارد زیر هنوز نیازمند تصمیم علمی/محصولی‌اند:

1. مقادیر رسمی α/β/γ برای Formula v1
2. mapping رسمی categorical labels به 0..100
3. آیا تمام Indicatorهای سند Required هستند یا برخی Optional
4. تعریف Staleness برای Sourceها
5. Quality policy برای Evidence
6. policy دقیق Preview در UI
7. calibration approval governance
8. scope انتخاب Formula در سطح ملی/استانی/منطقه‌ای

تا زمان تصمیم رسمی، Engine نباید این موارد را حدس بزند.

---

# 56. Definition of Done — PGOR Engine v1

PGOR Engine v1 زمانی آماده است که:

- تمام Indicatorهای سند Versioned Seed شده باشند.
- Raw score 0..100 validate شود.
- normalization تست شده باشد.
- Dimension aggregation تست شده باشد.
- P/G/O/R calculation تست شده باشد.
- Formula Version validation وجود داشته باشد.
- α+β+γ validation وجود داشته باشد.
- E calculation deterministic باشد.
- E band صحیح باشد.
- missing required data رفتار مشخص داشته باشد.
- unresolved conflict رفتار مشخص داشته باشد.
- Snapshot immutable باشد.
- Reproducibility test پاس شود.
- هیچ LLM call در Calculation path وجود نداشته باشد.
- Input/Formula/Engine versions در Snapshot ثبت شوند.

---

# 57. مرحله بعد

پس از این Spec:

```text
API Contracts v1
→ Event Contracts v1
→ Security / RBAC Matrix
→ Stack ADRs
→ Product Backlog
→ Sprint 1
```

اولین خروجی بعدی:

> **HAMOON_API_CONTRACTS_V1.md**
