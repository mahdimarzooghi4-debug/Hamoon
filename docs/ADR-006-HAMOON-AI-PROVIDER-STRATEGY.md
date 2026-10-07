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

Artifact یک artifact داخلی immutable و versioned است که با digest و lineage رجیستری
شناسایی می‌شود. baseline مصوب برای اولین implementation وزن‌دار:
`google/gemma-4-12B-it` با revision ثابت
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` و SHA-256 وزن
`5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d`
است. روش آموزش baseline، Supervised Fine-Tuning با LoRA/PEFT و serialization وزن adapter
به‌صورت Safetensors است.

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
- Training Run نسخه‌دار با وضعیت RUNNING/SUCCEEDED/FAILED و audit/event کامل؛
- فقط Training Run موفق حق ایجاد Model Candidate دارد؛ ثبت دستی artifact digest از API ممنوع است؛
- هسته Internal Model Executor برای اجرای executorهای صریحاً ثبت‌شده به‌صورت in-process؛
- artifact store خصوصی با آدرس‌دهی SHA-256، immutable identity و digest attestation؛
- Production artifact store فقط S3-compatible خصوصی روی HTTPS با credential واقعی است؛
- execution mode مصوب فقط `IN_PROCESS` داخل backend/worker خود Hamoon است؛
- هیچ network hop، endpoint، token یا inference service برای اجرای مدل مجاز نیست؛
- artifact از Registry lineage و digest معتبر resolve می‌شود، نه از URL یا endpoint؛
- fail-safe در نبود Production Model یا executor concrete؛
- ایجاد `AI_FALLBACK` Human Work Item هنگام unavailable بودن AI Production.

تصمیم baseline این مرحله:

- model family: `Gemma 4`؛
- model: `google/gemma-4-12B-it`؛
- immutable upstream revision:
  `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`؛
- pinned model weight SHA-256:
  `5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d`؛
- pinned tokenizer SHA-256:
  `cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f`؛
- training method: `SFT_LORA` با PEFT؛
- adapter serialization: Safetensors؛
- Hamoon artifact format: `HAMOON_GEMMA4_PEFT_SAFETENSORS_V1`؛
- pipeline identity: `gemma4-12b-it-sft-lora-v1`؛
- concrete execution: Transformers/PyTorch/PEFT به‌صورت `IN_PROCESS` و
  `local_files_only=True`؛
- base checkpoint از filesystem خصوصی/mounted artifact storage خوانده می‌شود و قبل از load
  revision، SHA-256 وزن و tokenizer، presenceِ chat template و metadata اصلی
  model/processor/tokenizer/generation verify می‌شوند؛ هیچ download شبکه‌ای در runtime انجام
  نمی‌شود؛
- Production Runtime Preflight باید هویت دقیق همین checkpoint را شامل model/revision/digestها
  با `execution_mode=IN_PROCESS` و `network_model_download=false` attest کند؛ receipt با هویت
  متفاوت قابل قبول نیست؛
- همان preflight باید provisioning checkpoint را نیز attest کند: filesystem محلی خصوصی،
  read-only، مسیر absolute غیر-root، verification id/timestamp معتبر و بدون network model
  download. vendor، mount path و hardware sizing در قرارداد hard-code نمی‌شوند؛
- Production internal-model artifact store نیز باید در preflight به‌صورت مستقل attest شود:
  S3-compatible روی remote HTTPS، bucket خصوصی، credential از runtime secret، namespace
  `internal-model-artifacts/sha256/`، create-only write semantics، SHA-256 content addressing
  و read-time digest verification. receipt فقط `credential_binding_id` غیرمحرمانه را ثبت
  می‌کند و raw access/secret key حق ورود به deployment evidence ندارد.

مقادیر زیر عمداً hard-code نشده‌اند و باید از configuration صریح تأمین شوند:

- LoRA rank/alpha/dropout/target modules/bias؛
- optimizer، learning rate، epoch، batch/accumulation، scheduler و سایر TrainingArguments؛
- generation arguments مانند `max_new_tokens`؛
- hardware sizing/resource isolation؛
- concrete production S3 provider/credentials و bucket deployment.

هسته execution/training و concrete Gemma trainer/executor اکنون وجود دارند، اما تا زمانی
که checkpoint خصوصی و configuration کامل runtime و artifact-store Production provision نشده
باشند، Production همچنان fail-closed است و به انسان route می‌شود.

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

Offline Evaluation باید به Model Version و evidence نسخه‌دار متصل باشد. Evaluation Run جدید
فقط از مسیر Admin و با Dataset Version در وضعیت `APPROVED`، purpose هم‌راستا، Candidate داخلی
دارای training lineage، Prompt Policy در وضعیت `ACTIVE` و evaluation policy version صریح
ایجاد می‌شود. Evaluation Dataset نباید همان Training Dataset باشد؛ هم Dataset Version ID و هم
manifest digest باید مستقل باشند تا training-data reuse به‌عنوان Evaluation fail-closed شود.
creation به‌تنهایی هیچ Promotion یا Production activation انجام نمی‌دهد.

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

model family، upstream revision، training method، artifact format و concrete
trainer/executor برای baseline v1 تصویب و پیاده شده‌اند. Production preflight نیز به هویت
checkpoint، provisioning attestation آن و artifact-store attestation bind شده است. مسیر
ایجاد Evaluation Run نیز به Dataset/Model/Prompt lineage واقعی bind شده است. موارد باز: مقادیر
hyperparameter، resource isolation/hardware sizing، provisioning فیزیکی/mount واقعی checkpoint
خصوصی، استقرار واقعی provider/bucket/credentials برای Production artifact store و جزئیات
policy/metric ارزیابی که فقط باید از تصمیم محصول و evidence واقعی تعیین شوند.

Dataset تأییدشده از طریق Training Run وارد Gemma 4 trainer می‌شود؛ adapter خروجی در storage
خصوصی immutable ثبت می‌شود و همان Run در صورت موفقیت Candidate lineage را می‌سازد. Training
هیچ Promotion خودکاری انجام نمی‌دهد. Executor فقط checkpoint محلیِ digest-pinned و adapter
داخلی را load می‌کند و هیچ network model fallback ندارد.

تا زمانی که checkpoint و config کامل runtime provision نشده باشد، مسیر AI fail-closed باقی
می‌ماند و Human Work Item ایجاد می‌شود.
