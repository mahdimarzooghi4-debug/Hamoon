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
