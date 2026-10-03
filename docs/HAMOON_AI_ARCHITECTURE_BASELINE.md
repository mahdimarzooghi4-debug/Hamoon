# Hamoon — Product & AI Architecture Baseline

> وضعیت: Concept / Business Architecture Baseline  
> هدف: ثبت تصمیم‌های معماری و محصولی تا این مرحله برای «ماشین توانمندسازی هوشمند هامون»

## 1. تعریف هامون

هامون یک چت‌بات عمومی نیست. هامون «ماشین توانمندسازی هوشمند» و لایه هوشمندی مسیر توانمندسازی خانوار است.

هسته نظری و تصمیم‌گیری آن بر چارچوب PGOR بنا می‌شود:

- **P — Participation / مشارکت**
- **G — Growth Capacity / ظرفیت رشد**
- **O — Opportunity / فرصت**
- **R — Resilience / تاب‌آوری**

هامون باید وضعیت خانوار را در طول زمان بسنجد، گلوگاه‌ها را تشخیص دهد، مسیر را تحلیل کند، گزینه‌های مداخله را پیشنهاد کند، خانوار را به خدمت تخصصی مناسب ارجاع دهد، نتیجه را دریافت و مستقل ارزیابی کند و از چرخه‌های قبلی یاد بگیرد.

## 2. اصل معماری

هامون باید **Orchestrator مسیر توانمندسازی خانوار** باشد، نه Orchestrator داخلی کسب‌وکارهای تخصصی.

کسب‌وکارهای تخصصی مستقل هستند. هر کدام می‌توانند سیستم، فرآیند و حتی AI اختصاصی خودشان را داشته باشند. معماری داخلی یا AI آن‌ها جزو Hamoon نیست.

رابطه Hamoon با Providerها فقط از طریق قراردادهای مشخص سرویس و داده انجام می‌شود:

```text
Discover → Match → Refer → Deliver → Receive Result → Measure Outcome → Learn
```

اصل مرزی:

> Hamoon owns the empowerment decision loop.  
> Specialized businesses own their service delivery loop.

## 3. حلقه اصلی هامون

```text
ASSESS
  ↓
DIAGNOSE
  ↓
PRESCRIBE
  ↓
MATCH
  ↓
REFER
  ↓
DELIVER
  ↓
MEASURE
  ↓
LEARN
  ↺
```

### Assess
جمع‌آوری وضعیت خانوار و ساخت Snapshot زمانی.

### Diagnose
تحلیل PGOR، نیازها، ظرفیت‌ها، محدودیت‌ها، ریسک‌ها و گلوگاه‌های توانمندسازی.

### Prescribe
تولید گزینه‌های مداخله مناسب، با امکان توضیح چرایی پیشنهاد و نگه‌داشتن انسان در حلقه تصمیم.

### Match
یافتن Provider مناسب بر اساس نوع خدمت، شرایط پذیرش، ظرفیت، دسترس‌پذیری و داده‌های عملکرد قبلی.

### Refer
ساخت Referral استاندارد و ارسال حداقل داده لازم و مجاز به Provider.

### Deliver
ارائه خدمت توسط کسب‌وکار تخصصی مستقل.

### Measure
دریافت Provider Result و سپس ارزیابی مستقل وضعیت خانوار توسط Hamoon.

### Learn
ثبت رابطه State → Intervention → Provider → Result → Outcome و استفاده از آن برای بهبود تصمیم‌های آینده.

## 4. معماری مفهومی Hamoon AI

```text
Household
   ↓
Household Digital Twin
   ↓
PGOR Engine
   ↓
Diagnosis / Needs Engine
   ↓
Prediction Engine
   ↓
Simulation Engine
   ↓
Prescription Engine
   ↓
Service Matching & Referral Engine
   ↓
Specialized Provider
   ↓
Provider Result
   ↓
Hamoon Re-assessment
   ↓
Actual Outcome
   ↓
Learning Engine
   ↺
```

LLM/Copilot لایه تعامل، توضیح، خلاصه‌سازی، بازیابی دانش و Tool Calling است؛ نباید جای موتور محاسباتی PGOR یا مدل‌های تخصصی تصمیم را بگیرد.

## 5. Household Intelligence

Hamoon باید برای هر خانوار یک وضعیت دیجیتال زمان‌مند نگهداری کند، نه فقط آخرین رکورد.

نمونه مفهومی:

```text
Household
├── Household Profile
├── Members
├── Assessments
├── PGOR Snapshots
├── Needs
├── Risks
├── Capacities
├── Constraints
├── Interventions
├── Referrals
├── Provider Results
├── Hamoon Outcomes
└── Timeline / Events
```

هدف این است که Hamoon علاوه بر «وضعیت فعلی»، مسیر حرکت خانوار (Empowerment Trajectory) را نیز بفهمد.

## 6. موتورهای هوشمندی

### 6.1 PGOR Engine
محاسبات قطعی و نسخه‌بندی‌شده PGOR. LLM نباید امتیازها را حدس بزند.

### 6.2 Diagnostic / Needs Engine
تشخیص نیاز، ریسک، ظرفیت، محدودیت و گلوگاه اصلی خانوار.

### 6.3 Prediction Engine
در صورت وجود داده معتبر کافی، برآورد مسیرهای آینده همراه با عدم‌قطعیت و محدودیت مدل.

### 6.4 Simulation Engine
بررسی سناریوهای What-if برای مداخلات مختلف، در صورت وجود مدل و داده معتبر.

### 6.5 Prescription Engine
تولید گزینه‌های مداخله و دلایل/شواهد مربوط به آن‌ها؛ تصمیم‌های حساس باید Human-in-the-loop باقی بمانند.

### 6.6 Service Matching & Referral Engine
اتصال Need/Intervention به Provider مناسب.

### 6.7 Outcome Engine
تفکیک نتیجه گزارش‌شده توسط Provider از Outcome واقعی مورد سنجش Hamoon.

### 6.8 Learning Engine
یادگیری کنترل‌شده از تاریخچه پرونده‌ها، مداخلات، Providerها و Outcomeها، با ارزیابی و نسخه‌بندی مدل.

## 7. اکوسیستم کسب‌وکارهای تخصصی

نمونه‌های فعلی مطرح‌شده:

| حوزه نیاز | کسب‌وکار تخصصی نمونه |
|---|---|
| حمایت غذایی | حنا |
| آموزش فرزندان | دنا |
| اجاره / مسکن | چارخونه |
| بازار / فروش | نگارین |

این نگاشت ثابت و Hard-coded نیست. در آینده می‌تواند برای هر نوع خدمت چند Provider وجود داشته باشد.

### Provider مستقل است

مثلاً:

```text
Hamoon
   ↓ Referral
حنا
   ├── Internal System
   ├── Internal Processes
   └── Internal AI (optional)
   ↓ Provider Result
Hamoon
```

Hamoon نباید وابسته به تکنولوژی داخلی Provider باشد.

## 8. Provider Intelligence

هر Provider در Hamoon باید پروفایل سرویس داشته باشد، از جمله:

- Provider identity
- Service catalog
- Eligibility rules
- Coverage / scope
- Current capacity / availability
- SLA
- Cost model (در صورت نیاز)
- Referral interface/API
- Result contract
- Historical referral data
- Observed outcome history

Hamoon باید بتواند از نتایج تاریخی بفهمد هر Provider برای چه نوع پرونده‌ها و شرایطی چه نتایج مشاهده‌شده‌ای داشته است. این داده نباید به یک «امتیاز کلی» ساده تقلیل داده شود.

## 9. قرارداد داده دوطرفه

```text
HAMOON ───── Referral ─────→ PROVIDER
HAMOON ←── Provider Result ─ PROVIDER
```

Provider باید حداقل چرخه وضعیت Referral را برگرداند:

```text
Created
→ Received
→ Accepted / Rejected
→ Service Started
→ Service Delivered
→ Completed / Failed / Cancelled
→ Result Submitted
```

Schema دقیق در مرحله Technical Architecture تعریف می‌شود.

## 10. Provider Result با Hamoon Outcome یکی نیست

اصل مهم:

```text
Provider Result ≠ Hamoon Outcome
```

مثال:

- «بسته غذایی تحویل شد» = Output / Provider Result
- «امنیت غذایی خانوار پس از مداخله بهبود یافت» = Outcome
- «تغییر پایدار در وضعیت مرتبط PGOR مشاهده شد» = Hamoon-measured impact

بنابراین Hamoon نباید ادعای موفقیت Provider را بدون Re-assessment به‌عنوان Outcome نهایی بپذیرد.

## 11. Matching مبتنی بر داده

Matching اولیه می‌تواند Rule-based باشد:

```text
Need
+ Eligibility
+ Service Type
+ Coverage
+ Capacity
→ Candidate Providers
```

با انباشت داده، Matching می‌تواند از تاریخچه نیز استفاده کند:

```text
Household State
+ PGOR
+ Need
+ Context
+ Intervention
+ Provider
+ Historical Outcomes
→ Evidence-informed Matching
```

هر پیشنهاد باید قابل توضیح و Audit باشد. برای تصمیم‌های حساس، انتخاب/تأیید نهایی باید در اختیار نقش انسانی مجاز باقی بماند.

## 12. داده یادگیری اصلی Hamoon

واحد یادگیری پیشنهادی:

```text
State(t)
+ Context(t)
+ PGOR(t)
+ Diagnosed Need
+ Recommended Intervention
+ Human Decision
+ Selected Provider
+ Referral
+ Service Execution
+ Provider Result
+ Outcome(t+n)
+ Re-assessment
+ Data Quality / Evidence
```

این تاریخچه یکی از دارایی‌های اصلی Hamoon Intelligence خواهد بود.

## 13. Human-in-the-loop

AI نقش تصمیم‌یار دارد.

Hamoon می‌تواند:

- خلاصه کند؛
- طبقه‌بندی کند؛
- نیاز و ریسک را شناسایی کند؛
- گلوگاه را توضیح دهد؛
- گزینه مداخله پیشنهاد کند؛
- Providerهای واجد شرایط را پیدا کند؛
- شواهد و نتایج تاریخی مرتبط را نمایش دهد؛
- روند و Outcome را پایش کند.

اما تصمیم‌های حساس، اشتراک داده، Override، تأیید مداخلات مهم و مواردی که سیاست محصول تعیین می‌کند باید توسط نقش انسانی مجاز کنترل شوند.

## 14. اصول داده و حریم خصوصی

ارجاع به Provider به معنی انتقال کل پرونده خانوار نیست.

باید اصول زیر رعایت شوند:

- Data minimization
- Purpose limitation
- Consent / lawful authorization
- Role-based access
- Field-level access where needed
- Audit log
- Referral-specific data sharing
- Provider isolation
- Model/version traceability

هر Provider فقط داده‌ای را دریافت می‌کند که برای اجرای همان خدمت لازم و مجاز است.

## 15. Network Learning Effect

```text
More Referrals
   ↓
More Execution Data
   ↓
More Outcomes
   ↓
Better Evidence
   ↓
Better Diagnosis / Matching / Prediction
   ↓
Better-informed Interventions
   ↓
More Outcomes
   ↺
```

این حلقه باید با کنترل کیفیت داده، ارزیابی مدل، جلوگیری از Bias و امکان Human Override مدیریت شود.

## 16. جایگاه AI کسب‌وکارهای تخصصی

هر Provider می‌تواند AI خودش را داشته باشد یا نداشته باشد.

```text
Hamoon AI ≠ Hana AI
Hamoon AI ≠ Dana AI
Hamoon AI ≠ Charkhooneh AI
Hamoon AI ≠ Negarin AI
```

هیچ وابستگی معماری بین مدل داخلی آن‌ها و Hamoon لازم نیست.

Integration Contract باید Technology Agnostic باشد.

## 17. تصویر نهایی

```text
                    HAMOON
                      │
             Empowerment Intelligence
                      │
      ┌───────────────┼────────────────┐
      │               │                │
 Household       PGOR/Decision     Provider
 Intelligence    Intelligence      Intelligence
      │               │                │
      └───────────────┼────────────────┘
                      ↓
                 Referral Layer
                      ↓
       ┌──────────────┼───────────────┐
       ↓              ↓               ↓
      حنا            دنا           چارخونه
  Food Support    Education        Housing
       │              │               │
       └──────────────┼───────────────┘
                      ↓
                    نگارین
                 Market/Sales
                      │
                      ↓
                Provider Results
                      ↓
               Hamoon Outcomes
                      ↓
                Learning Engine
                      ↺
```

## 18. مسیر توسعه

این Baseline باید در فرآیند مادر تولید محصول Hamoon به این ترتیب ادامه پیدا کند:

```text
Business
→ Technical
→ Scrum / Product Backlog
→ Sprint
→ Code
→ Code Review
→ Stage
→ QA / Testing
→ Release Approval
→ Production
→ Monitoring
→ Improvement
```

### گام بعدی

مرحله بعد، تبدیل این Baseline به **Hamoon AI Blueprint v1** و سپس Technical Architecture است؛ شامل Domain Model، API Contracts، Event Model، Referral State Machine، Outcome Schema، Provider Registry، Data Architecture، AI/ML boundaries، Security و Backlog.

## 19. Product Boundary: سامانه جامع توانمندسازی در اختیار مددکار

Hamoon صرفاً یک سیستم تشخیصی نیست؛ **سامانه جامع و هوشمند مدیریت مسیر توانمندسازی خانوار** است.

مرز نقش‌ها:

- **مددجو / خانوار:** موضوع توانمندسازی و صاحب مسیر؛ کاربر عملیاتی Hamoon نیست.
- **مددکار:** کاربر اصلی Hamoon و عامل انسانی تصمیم، اصلاح داده، تأیید/اصلاح نسخه و پیگیری مسیر.
- **Hamoon:** سامانه جامع مدیریت چرخه توانمندسازی و Decision Intelligence.
- **Specialized Providers:** ارائه‌دهندگان مستقل مداخلات و خدمات.

جامع بودن Hamoon در چرخه Backend و مدیریت مسیر است و الزاماً به معنی UI پیچیده نیست. تجربه مددکار می‌تواند حول جست‌وجوی کد ملی و مشاهده پرونده جامع توانمندسازی طراحی شود.

```text
مددکار
  ↓
کد ملی خانوار
  ↓
پرونده جامع توانمندسازی
  ↓
وضعیت + PGOR + روند
  ↓
تشخیص
  ↓
نسخه
  ↓
مداخلات / ارجاعات
  ↓
نتایج
  ↓
ارزیابی مجدد
  ↓
یادگیری
```

## 20. نقش مددکار در کیفیت و اصلاح داده

مددکار علاوه بر نقش توانمندسازی، **عامل انسانی اصلاح و کنترل کیفیت داده پرونده** نیز هست.

داده خانوار ممکن است قبلاً در Hamoon یا سامانه‌های دیگر ثبت شده باشد. اگر مددکار بر اساس اطلاعات یا شواهد جدید متوجه نادرستی یک مقدار شود، باید بتواند آن را اصلاح کند.

اصلاح داده نباید تاریخچه را حذف کند. Hamoon باید حداقل موارد زیر را نگه دارد:

- مقدار قبلی
- مقدار جدید
- منبع مقدار قبلی
- عامل اصلاح
- زمان اصلاح
- دلیل اصلاح
- مستند/شاهد مرتبط، در صورت وجود
- مقدار جاری مورد استفاده در محاسبات
- Audit Trail کامل

مددکار می‌تواند داده را تأیید، اصلاح یا در صورت وجود تعارض برای بررسی علامت‌گذاری کند. AI می‌تواند تعارض یا ناهنجاری را گزارش کند، اما صرفاً به دلیل غیرعادی بودن داده نباید آن را خودکار تغییر دهد.

## 21. اصل صحت داده — Presumption of Data Validity

اصل پایه Hamoon:

> **داده‌ها درست هستند، مگر اینکه خلاف آن ثابت شود.**

هر داده‌ای که از یک منبع مجاز وارد Hamoon می‌شود، به‌صورت پیش‌فرض صحیح و قابل استفاده در نظر گرفته می‌شود. Hamoon نباید تمام داده‌ها را تا زمان راستی‌آزمایی مجدد «مشکوک» یا «تأییدنشده» تلقی کند.

```text
Authorized Source Data
        ↓
Accepted by Default
        ↓
Used by Hamoon
        ↓
Evidence of Conflict / Error?
        │
   No ──┴── Yes
   ↓         ↓
Remain     Human Review
Accepted      ↓
          Confirm / Correct / Dispute
```

وضعیت‌های مفهومی پیشنهادی داده:

- **ACCEPTED:** حالت پیش‌فرض؛ داده معتبر فرض می‌شود.
- **CORRECTED:** خلاف مقدار قبلی احراز و مقدار اصلاح شده است.
- **DISPUTED:** تعارض یا ادعای خلاف وجود دارد ولی هنوز تعیین تکلیف نشده است.
- **SUPERSEDED:** رکورد تاریخی که مقدار جدید جایگزین آن شده است.

### اصل عدم حذف تاریخچه

اصلاح یک داده به معنی حذف مقدار قبلی نیست. مقدار قبلی باید برای Audit، تحلیل کیفیت منابع و بازسازی تصمیم‌های تاریخی حفظ شود.

### منشأ داده — Data Provenance

برای داده‌های مؤثر در تصمیم، Hamoon باید بتواند مشخص کند:

```text
Value
+ Source
+ Recorded At
+ Effective At
+ Changed By
+ Change Reason
+ Evidence (when applicable)
+ Status
+ Version / History
```

### استفاده در AI و PGOR

PGOR Engine، Diagnostic Engine، Prescription Engine و سایر اجزای Hamoon از **Current Accepted Value** استفاده می‌کنند.

در صورت وجود `DISPUTED` data، سیستم باید متناسب با اهمیت آن داده، تعارض را به مددکار نشان دهد و در تصمیم‌های حساس عدم‌قطعیت را لحاظ کند.

AI می‌تواند بگوید:

> «بین دو منبع درباره وضعیت اشتغال تعارض وجود دارد؛ بررسی مددکار لازم است.»

اما نباید بدون Rule/Authority مشخص، مقدار رسمی پرونده را تغییر دهد.

## 22. تفکیک انواع داده خانوار

برای حفظ معنای داده، Hamoon باید منشأ و نوع آن را از هم تفکیک کند:

- **Declared Data:** داده اعلام‌شده توسط مددجو یا منبع اولیه.
- **Observed Data:** داده حاصل از مشاهده یا بررسی.
- **Corrected Data:** مقداری که پس از اثبات خلاف داده قبلی اصلاح شده است.
- **Derived Data:** داده محاسبه یا استنباط‌شده توسط Hamoon، مانند PGOR، E، Risk، Diagnosis یا Prediction.

این دسته‌بندی به معنی مشکوک بودن Declared Data نیست. مطابق اصل صحت داده، همه داده‌های مجاز در حالت عادی قابل استفاده‌اند مگر اینکه خلافشان ثابت شود.

## 23. پیامد معماری

با این اصول، Hamoon فقط Data Consumer نیست. Hamoon باید یک **Family Data & Empowerment System of Record** با قابلیت Data Integration، Provenance، Versioning، Correction، Audit و Decision Intelligence باشد.

```text
External / Existing Systems
          ↓
     Family Data
          ↓
 Presumption of Validity
          ↓
       HAMOON
          ↕
       مددکار
  (Correction / Review)
          ↓
Current Family State
          ↓
PGOR / Diagnosis / Prescription
          ↓
Intervention / Outcome / Learning
```

این اصول باید در طراحی Domain Model، Data Architecture، API Integration، Security، Audit Log و AI Guardrails رعایت شوند.

## 24. اصل AI-First — هامون یک سیستم هوشمند تصمیم‌یار است

از این مرحله به بعد، تمام تصمیم‌های فنی Hamoon باید بر این اصل استوار باشند:

> **Hamoon یک نرم‌افزار معمولی نیست که بعداً AI به آن اضافه شود؛ Hamoon از ابتدا یک سیستم هوشمند تصمیم‌یار و یادگیرنده است و UI، داده، Workflow و Integrationها برای تغذیه، کنترل و بهبود حلقه هوشمندی آن طراحی می‌شوند.**

معماری پایه باید این زنجیره را پشتیبانی کند:

```text
Data Sources
    ↓
Temporal Household State
    ↓
Feature / Evidence Layer
    ↓
PGOR Engine
    ↓
Intelligence Layer
 ├─ Diagnosis
 ├─ Prediction
 ├─ Simulation
 ├─ Prescription
 ├─ Provider Matching
 └─ Outcome Intelligence
    ↓
Human Decision
    ↓
Action / Referral
    ↓
Observed Result
    ↓
Re-assessment
    ↓
Learning Signal
    ↺
```

### 24.1 تفکیک موتور قطعی از AI

همه اجزای هوشمندی از یک جنس نیستند:

- **PGOR Engine و محاسبه E باید Deterministic، Versioned و Reproducible باشند.**
- LLM یا مدل‌های مولد نباید P/G/O/R/E را حدس بزنند.
- Diagnosis، Prediction، Simulation، Prescription، Provider Matching و Outcome Intelligence می‌توانند از AI/ML استفاده کنند، اما باید Evidence-aware، Versioned، قابل ارزیابی و قابل Override باشند.
- هر خروجی AI مؤثر در تصمیم باید حداقل Model Version، Input State Version، Evidence، Confidence/Uncertainty در صورت کاربرد، و Human Decision بعدی را قابل ردیابی کند.

### 24.2 اجزای فنی AI که از V1 باید جزو معماری باشند

Technical Architecture Hamoon باید از ابتدا برای این اجزا جای مشخص داشته باشد:

- **Temporal Household State / Feature Layer**
- **PGOR Engine**
- **AI Gateway / Intelligence Orchestrator**
- **Model Registry**
- **Prompt / Policy Registry** برای اجزای LLM-based
- **Decision Trace**
- **Evaluation Framework**
- **Feedback & Learning Store**
- **Model / Data Monitoring**
- **Guardrails & Human Override**
- **Model and Feature Versioning**

این اجزا Feature جانبی یا فاز تزئینی آینده نیستند؛ بخشی از Platform Architecture هامون هستند.

### 24.3 Human Decision به‌عنوان داده یادگیری

تصمیم انسان فقط Audit Log نیست؛ در صورت تعریف صحیح، یکی از Learning Signalهای اصلی Hamoon است.

نمونه:

```text
AI Diagnosis
→ Human Review
→ Confirm / Modify / Replace
→ Reason
→ Intervention
→ Outcome Later
→ Learning Signal
```

همین الگو باید برای موارد زیر نیز قابل ثبت باشد:

- Diagnosis
- Prescription
- Provider Matching / Selection
- Referral decisions
- Outcome interpretation
- Data conflict resolution

### 24.4 یادگیری به معنی Retrain خودکار نیست

ثبت Learning Signal به معنی تغییر فوری مدل Production نیست.

چرخه صحیح:

```text
Production Signals
→ Curated Learning Dataset
→ Offline Evaluation
→ Model / Rule Candidate
→ Validation
→ Approval
→ Versioned Deployment
→ Monitoring
```

هر تغییر در مدل، Rule، Prompt یا وزن‌های تصمیم‌گیری باید قابل نسخه‌بندی، ارزیابی، Rollback و Audit باشد.

### 24.5 نتیجه برای Technical Architecture

سند Technical Architecture نباید فقط شامل Backend، Database و API باشد. ساختار آن باید حداقل این لایه‌ها را پوشش دهد:

```text
System Architecture
→ Intelligence Architecture
→ Temporal Data Architecture
→ PGOR Engine
→ AI Engines
→ Human-in-the-loop
→ Learning Architecture
→ Model Evaluation
→ APIs / Events
→ Security
→ Deployment
→ Observability
```

اصل نهایی:

> **We are building an empowerment decision-and-learning machine, not a CRUD system with AI features.**
