# ADR-006 — Hamoon Native AI Runtime & Governed Learning

> وضعیت: Accepted — supersedes the former external-provider strategy  
> دامنه تصمیم: Production AI runtime, model artifacts, learning, evaluation, promotion, sovereignty  
> اصل حاکم: **AI هامون در Production به هیچ API داخلی یا خارجی متصل نمی‌شود.**

---

# 1. Context

هامون یک سامانه ملی است. بنابراین availability، محرمانگی و استمرار خدمت نباید به اینترنت
بین‌الملل، یک Vendor خارجی، یک API داخلی جداگانه یا یک سرویس inference شبکه‌ای وابسته باشد.

AI هامون باید بتواند در شبکه بسته و حتی در قطع کامل اینترنت بین‌الملل به کار خود ادامه دهد.

PGOR همچنان deterministic و مستقل از AI است. AI فقط proposal تولید می‌کند و تصمیم انسانی
برای Diagnosis، Prescription و Outcome الزامی است.

---

# 2. Non-negotiable Architecture Rule

Production AI:

```text
NO external AI API
NO internal AI API
NO HTTP/gRPC inference dependency
NO network fallback
NO vendor SDK
NO silent model switch
```

Runtime مجاز:

```text
Hamoon application
→ local immutable model artifact
→ in-process HAMOON_NATIVE engine
→ structured proposal
→ schema/domain guardrails
→ Human Review
```

Development/Test می‌تواند از `FakeAIProvider` deterministic استفاده کند، اما Production فقط
`HAMOON_NATIVE` را می‌پذیرد.

---

# 3. Native Model Artifact

هر نسخه مدل یک artifact داخلی و immutable است.

حداقل identity:

```text
model_id
task_class
feature_schema_version
output_schema_version
training_dataset_id
training_dataset_manifest_digest
trained_at
artifact_sha256
engine_version
```

Artifact با SHA-256 content-addressed ذخیره می‌شود.

Production routing بدون `artifact_sha256` معتبر قابل فعال‌شدن نیست.

---

# 4. Model Store

Production model root باید:

- local/internal filesystem or mounted internal persistent volume باشد؛
- absolute path داشته باشد؛
- خارج از `/tmp` و root filesystem باشد؛
- توسط release/runtime policy کنترل شود؛
- برای inference به network download نیاز نداشته باشد.

Runtime هیچ model download انجام نمی‌دهد.

---

# 5. Native Inference

`HAMOON_NATIVE` مدل را مستقیم از artifact محلی load می‌کند.

Production inference:

```text
Feature Package
→ resolve ACTIVE native route
→ verify model artifact SHA-256
→ load local artifact
→ native inference
→ JSON Schema validation
→ domain grounding/guardrails
→ persist AI Decision
→ Human Review
```

اگر artifact وجود نداشته باشد، digest mismatch باشد، schema ناسازگار باشد یا نمونه آموزشی
قابل‌اعتماد پیدا نشود، inference **fail closed** می‌شود.

AI حق حدس‌زدن داده‌ی مفقود را ندارد.

---

# 6. Learning / Growth Model

هامون به مرور زمان از داده‌های واقعی و تصمیم‌های انسانی رشد می‌کند، اما Production model
مستقیماً و online تغییر نمی‌کند.

مسیر اجباری:

```text
Real Operations
→ Human Review
→ Learning Signal RAW
→ Human Curation
→ CURATED Signal
→ Versioned Dataset DRAFT
→ Human Dataset Approval
→ Native Offline Training
→ Immutable Model Artifact
→ Model CANDIDATE
→ Offline Evaluation
→ PASSED Gate
→ Routing Policy DRAFT
→ Explicit ADMIN Promotion
→ PRODUCTION
```

هیچ مرحله‌ای اجازه self-promotion ندارد.

---

# 7. Training Sources

برای Diagnosis و Prescription فقط Learning Signalهای زیر مجازند:

- CURATED
- دارای AI Decision معتبر
- دارای Human Decision معتبر
- دارای accepted structured payload
- دارای Feature Package معتبر

برای Outcome:

- فقط `CURATED OUTCOME_OBSERVED`
- reviewed Outcome
- `causal_claim=false`
- Provider free text وارد dataset نمی‌شود.

---

# 8. Case Identity Removal

Model artifact نباید case identity نگه دارد.

هنگام training:

- UUIDهای پرونده به‌صورت recursive حذف می‌شوند؛
- case-specific refs حذف/نرمال می‌شوند؛
- Prescription diagnosis refs به `diagnosis:CURRENT` تبدیل می‌شوند؛
- source/provenance IDs داخل dataset باقی می‌مانند اما وارد inference artifact نمی‌شوند.

Artifact شامل pattern/feature/target لازم برای مدل است، نه هویت Household.

---

# 9. Feature Coverage / No Guessing

Native inference فقط وقتی مجاز است که training example برای شکل feature package جاری coverage
کامل داشته باشد.

اگر featureهای لازم در training example موجود نباشند یا هیچ example قابل اعمالی وجود نداشته
باشد:

```text
NATIVE_MODEL_NO_APPLICABLE_TRAINING_EXAMPLE
```

و proposal تولید نمی‌شود.

این رفتار عمداً fail-safe است.

---

# 10. Task Classes

V1 native trainable tasks:

```text
DIAGNOSIS
PRESCRIPTION
OUTCOME_INTERPRETATION
```

هر Task Class:

- Feature Schema مستقل
- Output Schema مستقل
- Dataset مستقل
- Model Version مستقل
- Evaluation مستقل
- Routing Policy مستقل

دارد.

---

# 11. PGOR Boundary

AI هرگز:

- P/G/O/R/E را محاسبه نمی‌کند؛
- PGOR را تغییر نمی‌دهد؛
- formula/scoring definition را انتخاب نمی‌کند؛
- missing PGOR input را حدس نمی‌زند.

فقط persisted OFFICIAL PGOR و Feature Package نسخه‌دار را مصرف می‌کند.

---

# 12. Diagnosis Boundary

Diagnosis AI:

- proposal تولید می‌کند؛
- grounded feature refs اجباری است؛
- Human Review اجباری است؛
- Confirm/Modify/Replace توسط انسان انجام می‌شود؛
- accepted diagnosis جدا از machine proposal ذخیره می‌شود.

---

# 13. Prescription Boundary

Prescription AI:

- فقط accepted diagnosis + persisted PGOR feature package را مصرف می‌کند؛
- intensity score supplied by Hamoon را تغییر نمی‌دهد؛
- Provider انتخاب نمی‌کند؛
- Intervention فعال نمی‌کند؛
- Referral ارسال نمی‌کند؛
- Human Review اجباری است.

---

# 14. Outcome Boundary

Outcome AI:

- فقط observed change را تفسیر می‌کند؛
- `causal_claim=false` اجباری است؛
- Provider free text وارد model input/training artifact نمی‌شود؛
- Human Review اجباری است.

---

# 15. AI Decision Provenance

هر persisted AI Decision باید حداقل این identity را نگه دارد:

```text
provider_code = HAMOON_NATIVE
model_id
model_artifact_sha256
model_alias
routing_policy_id/version
prompt_policy_version
output_schema_version
feature_package_id
trace_id
generated_at
```

بنابراین هر proposal قابل بازسازی و audit است.

---

# 16. Model Registry

Production registry فقط `HAMOON_NATIVE` provider فعال را برای AI decision-producing tasks
می‌پذیرد.

Legacy external provider records برای historical audit ممکن است در DB باقی بمانند، اما:

```text
status = DISABLED
```

و model/routingهای legacy:

```text
status = RETIRED
```

می‌شوند.

---

# 17. Promotion Guard

Promotion به Production فقط وقتی مجاز است که:

- provider = `HAMOON_NATIVE`
- provider status = ACTIVE
- artifact_sha256 معتبر باشد
- model status = CANDIDATE | APPROVED
- Prompt Policy = ACTIVE
- Evaluation = PASSED
- dataset manifest digest ثبت شده باشد
- evaluation report digest ثبت شده باشد
- structural gate passed باشد
- Routing Policy = DRAFT
- ADMIN صریحاً Promote کند

Passed Evaluation به‌تنهایی Production را تغییر نمی‌دهد.

---

# 18. No Fallback

Production AI fallback شبکه‌ای ندارد.

اگر Native AI unavailable باشد:

```text
fail closed
→ operational failure event
→ human work/review path
```

نه:

```text
fallback to OpenAI
fallback to internal HTTP model server
fallback to another vendor
```

---

# 19. Offline Evaluation

Candidate evaluation باید روی runner داخلی/کنترل‌شده اجرا شود و artifact local را با digest دقیق
مصرف کند.

Evaluation هیچ API key و inference endpoint نمی‌گیرد.

Evidence شامل:

- commit SHA
- model ID
- artifact SHA-256
- output digest
- report digest

است.

---

# 20. Production Configuration

Production startup:

- وجود external AI credential را رد می‌کند؛
- `HAMOON_AI_MODEL_ROOT` معتبر و absolute را الزام می‌کند؛
- inference network endpoint ندارد.

Production runtime preflight باید وجود native model store را بررسی کند.

---

# 21. Security

- هیچ prompt/input به سرویس AI بیرونی ارسال نمی‌شود.
- هیچ API credential برای AI Production وجود ندارد.
- model artifact content-addressed است.
- artifact tampering با SHA-256 رد می‌شود.
- case identity از training artifact حذف می‌شود.
- raw PII وارد logs/metrics نمی‌شود.

---

# 22. Observability

Metrics همچنان task/model/routing-level هستند، اما provider dimension در Production مقدار ثابت:

```text
HAMOON_NATIVE
```

دارد.

هیچ telemetry AI نباید Household PII یا model training case identity حمل کند.

---

# 23. Rollback

Rollback یعنی:

```text
previous evaluated native model artifact
+ previous approved routing policy
```

فعال شود.

Rollback به external service مجاز نیست.

---

# 24. Growth Does Not Mean Autonomous Authority

«رشد AI» یعنی quality/model artifact با داده‌ی curated بهتر می‌شود.

به معنی این موارد نیست:

- AI خودش Accepted State را تغییر دهد؛
- AI خودش PGOR را تغییر دهد؛
- AI خودش Dataset را approve کند؛
- AI خودش مدل را Promote کند؛
- AI خودش Provider انتخاب کند؛
- AI خودش Production policy را عوض کند.

Human governance همیشه بیرون از model باقی می‌ماند.

---

# 25. Current V1 Native Engine

V1 runtime یک engine بومی content-addressed و in-process دارد که از reviewed case patterns در
artifact استفاده می‌کند.

این engine یک boundary پایدار برای رشد آینده است؛ اگر بعداً engine قوی‌تر داخلی ساخته شود،
همان governance حفظ می‌شود:

```text
local artifact
→ no network inference
→ versioned evaluation
→ explicit human promotion
```

تغییر engine بدون Evaluation و artifact version جدید مجاز نیست.

---

# 26. Consequence

Hamoon Production AI باید بتواند با قطع کامل اینترنت بین‌الملل و بدون هیچ AI API به کار ادامه
دهد، مشروط به اینکه زیرساخت داخلی خود سامانه، database/workflow و model artifact store در دسترس
باشند.

این ADR برای تمام implementationهای بعدی AI در هامون الزام‌آور است.


---

# 27. Model Growth Lineage

رشد مدل بومی باید lineage صریح داشته باشد.

نسخه جدید می‌تواند فقط از یک Model Version والد با وضعیت:

```text
APPROVED | PRODUCTION
```

ساخته شود.

روند رشد:

```text
Parent Native Artifact
+ New APPROVED Dataset
→ New Immutable Native Artifact
→ New CANDIDATE Model Version
→ Offline Evaluation
→ Human Promotion
```

نسخه جدید مثال‌های معتبر والد را حفظ می‌کند، مثال‌های Dataset جدید را اضافه می‌کند و
duplicateهای یکسان را دوباره وارد artifact نمی‌کند.

هویت lineage در دو لایه ثبت می‌شود:

- `parent_model_version_id` در Model Registry؛
- `parent_artifact_sha256` داخل Native Model Artifact.

این lineage به معنی online learning یا self-promotion نیست. هر نسل جدید همچنان باید تمام
Evaluation و Promotionهای انسانی را طی کند.
