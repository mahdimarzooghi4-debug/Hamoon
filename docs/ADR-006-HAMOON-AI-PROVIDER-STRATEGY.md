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

Artifact در این مرحله یک artifact داخلی immutable و versioned است که با digest و lineage
رجیستری شناسایی می‌شود. فرمت serialization، خانواده مدل و محل فیزیکی ذخیره‌سازی هنوز انتخاب
نشده‌اند و نباید از روی implementation حدس زده شوند.

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

Dataset creation برای signalهای دارای policy مصوب به‌صورت event-driven و خودکار است: هر
Learning Signal که به `CURATED` می‌رسد، اگر برای نوع آن Dataset policy موجود باشد، همان لحظه
یک Dataset Version جدید و immutable در وضعیت `DRAFT` ساخته می‌شود. نسخه خودکار بر اساس
شناسه همان signal idempotent است. signalهایی که هنوز Dataset policy مصوب ندارند خودکار وارد
Dataset نمی‌شوند.

Dataset Approval همچنان انسانی است و Promotion به Production فقط با اقدام صریح ADMIN انسانی
انجام می‌شود.

---

# 5. Current Implementation Phase

در این مرحله فقط این قراردادها پیاده می‌شوند:

- حذف OpenAI و هر AI endpoint/token از مسیر Production؛
- تبدیل هویت runtime به `INTERNAL_MODEL`؛
- نگهداری Model Registry و lineage نسخه‌دار؛
- الزام artifact digest، training dataset digest، training pipeline version و evaluation evidence؛
- ثبت Candidate metadata و lineage نسخه‌دار؛
- ساخت event-driven و خودکار Dataset Versionهای DRAFT از Learning Signalهای CURATED واجد policy؛
- هسته Internal Training Engine برای اجرای trainerهای صریحاً ثبت‌شده به‌صورت in-process؛
- هسته Internal Model Executor برای اجرای executorهای صریحاً ثبت‌شده به‌صورت in-process؛
- artifact store contract با digest attestation و immutable artifact identity؛
- execution mode مصوب فقط `IN_PROCESS` داخل backend/worker خود Hamoon است؛
- هیچ network hop، endpoint، token یا inference service برای اجرای مدل مجاز نیست؛
- artifact از Registry lineage و digest معتبر resolve می‌شود، نه از URL یا endpoint؛
- fail-safe در نبود Production Model یا executor concrete؛
- ایجاد `AI_FALLBACK` Human Work Item هنگام unavailable بودن AI Production.

عمداً در این مرحله پیاده نمی‌شوند:

- مدل مشخص مانند Llama/Qwen/Mistral یا هر خانواده دیگر؛
- Training algorithm؛
- concrete trainer/model family و training algorithm؛
- concrete in-process executor implementation و inference algorithm؛
- threshold یا hyperparameter؛
- production artifact-store binding؛
- internal/external inference API.

هسته execution/training اکنون وجود دارد، اما تا زمانی که concrete trainer، executor و
artifact-store binding مصوب در process ثبت نشده باشند، Production همچنان fail-closed است و
به انسان route می‌شود.

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

Execution boundary تصویب شده است: مدل فقط به‌صورت `IN_PROCESS` داخل خود Hamoon اجرا می‌شود
و هیچ API/endpoint/token یا inference service جداگانه مجاز نیست.

مواردی که هنوز تصمیم جداگانه می‌خواهند: model family، artifact serialization format،
training method، concrete trainer/executor implementation، production artifact-store binding،
resource isolation و evaluation policy جزئی.

هسته Training/Execution این تصمیم‌ها را hard-code نمی‌کند. تا تصویب و ثبت صریح implementation
مشخص، Production route وجود مدل را کافی نمی‌داند و fail-closed باقی می‌ماند.
