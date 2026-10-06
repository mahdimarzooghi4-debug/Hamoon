# ADR-006 — Hamoon Internal Model Architecture & Governed Learning

> وضعیت: Accepted  
> دامنه تصمیم: Production AI architecture, model registry, learning governance, evaluation, promotion  
> اصل حاکم: **AI هامون جزئی از خود سامانه هامون است و در Production به هیچ API مدل خارجی یا داخلی وابسته نیست.**

---

# 1. Context

هامون یک Decision & Learning Machine ملی و مستقل است. AI نباید برای inference یا learning
به OpenAI، vLLM، TGI، یک سرویس inference جداگانه، یا هر endpoint/token مدل دیگری متکی باشد.

PGOR کاملاً deterministic و مستقل از AI باقی می‌ماند. AI حق محاسبه یا تغییر PGOR، حدس
داده مفقود، یا جایگزینی تصمیم انسانی را ندارد.

---

# 2. Non-negotiable Production Boundary

Production AI:

```text
NO external AI API
NO internal model API
NO inference endpoint/token
NO network model fallback
NO automatic self-promotion
```

هویت Production در Registry فقط:

```text
INTERNAL_MODEL
```

است. این نام یک vendor/provider نیست؛ نشان می‌دهد نسخه مدل بخشی از چرخه داخلی خود هامون است.

Development/Test می‌تواند از Fake deterministic برای تست قرارداد استفاده کند، اما Fake بخشی
از Production routing نیست.

---

# 3. Model Registry Contract

هر Model Version داخلی باید قبل از Evaluation و Promotion حداقل این lineage را داشته باشد:

```text
model version
artifact digest
training dataset manifest digest
training pipeline version
evaluation evidence
```

این ADR درباره فرمت artifact، خانواده مدل، الگوریتم Training، executor یا محل فیزیکی ذخیره‌سازی
آن تصمیم نمی‌گیرد.

هیچ Model Version بدون lineage کامل نمی‌تواند وارد Production شود.

---

# 4. Governed Learning Path

تنها مسیر مجاز رشد AI:

```text
Observed Outcomes
→ Human Review
→ Curated Learning Signals
→ Versioned Dataset
→ Internal Training Pipeline
→ Model Artifact
→ Offline Evaluation
→ Passed Gate
→ Human Approval
→ Versioned Production Model
→ Monitoring
→ New Learning Signals
```

یادگیری مستقیم از Production ممنوع است. رسیدن داده جدید، Passed شدن Evaluation یا ساخته‌شدن
artifact به‌تنهایی هیچ نسخه‌ای را Production نمی‌کند.

Promotion به Production فقط با اقدام صریح ADMIN انسانی انجام می‌شود.

---

# 5. Current Implementation Phase

در این مرحله فقط این قراردادها پیاده می‌شوند:

- حذف OpenAI و هر AI endpoint/token از مسیر Production؛
- تبدیل هویت runtime به `INTERNAL_MODEL`؛
- نگهداری Model Registry و lineage نسخه‌دار؛
- الزام artifact digest، training dataset digest، training pipeline version و evaluation evidence؛
- ثبت Candidate metadata بدون اجرای Training؛
- fail-safe در نبود Production Model یا executor مصوب؛
- ایجاد `AI_FALLBACK` Human Work Item هنگام unavailable بودن AI Production.

عمداً در این مرحله پیاده نمی‌شوند:

- مدل مشخص مانند Llama/Qwen/Mistral یا هر خانواده دیگر؛
- Training algorithm؛
- inference/execution algorithm؛
- threshold یا hyperparameter؛
- Training Engine کامل؛
- internal/external inference API.

بنابراین تا تصویب مرحله بعد، executor داخلی عمداً unavailable است و Production به انسان
fail-safe می‌شود.

---

# 6. Human Decision Boundary

AI فقط proposal می‌دهد. Accepted State، Diagnosis review، Prescription review، Provider
selection و Outcome review تصمیم انسانی یا deterministic سامانه هستند.

PGOR:

- توسط AI محاسبه نمی‌شود؛
- توسط AI تغییر نمی‌کند؛
- missing input آن توسط AI حدس زده نمی‌شود.

Outcome:

- فقط observed change را تفسیر می‌کند؛
- `causal_claim=false` اجباری است؛
- Human Review اجباری است.

Provider free text مستقیماً وارد Outcome AI learning dataset نمی‌شود.

---

# 7. Dataset Boundary

فقط Learning Signalهای Curated و مجاز وارد Dataset آموزشی می‌شوند.

برای Outcome فقط signalهای `CURATED OUTCOME_OBSERVED` مجازند و provenance انسانی باید
قابل ردیابی باشد.

Dataset نسخه‌دار است و Approval انسانی Dataset از Model Promotion مستقل می‌ماند.

---

# 8. Evaluation & Promotion Boundary

Offline Evaluation باید به Model Version و evidence نسخه‌دار متصل باشد.

Passed Gate فقط شرط لازم است، نه مجوز Production.

```text
Curated Dataset
→ Model Artifact
→ Offline Evaluation
→ PASSED
→ Routing Policy DRAFT
→ Explicit ADMIN Promotion
→ PRODUCTION
```

هر مسیر دیگری fail closed است.

---

# 9. Fail-safe

اگر برای Task Class موردنظر Production Model داخلی معتبر وجود نداشته باشد، lineage ناقص باشد،
یا executor مصوب هنوز موجود نباشد:

- inference انجام نمی‌شود؛
- هیچ مدل یا خروجی fallback حدسی انتخاب نمی‌شود؛
- درخواست با وضعیت unavailable برمی‌گردد؛
- `AI_FALLBACK` Human Work Item idempotent ساخته می‌شود.

این رفتار بخشی از safety contract هامون است، نه خطای موقت برای دورزدن.

---

# 10. Future Decision Required

ساخت Internal Training Pipeline و Internal Model Executor یک تصمیم معماری مستقل بعدی است.
پیش از آن باید به‌صورت صریح model family، artifact contract، training method، execution
semantics، resource isolation و evaluation policy تصویب شوند.

تا آن زمان هیچ implementation مشخصی حق ورود به Production path را ندارد.
