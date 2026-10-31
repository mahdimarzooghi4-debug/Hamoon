import { useMemo, useState } from "react";
import "./figma-queue-demo.css";

type QueueKind = "ارجاع" | "تصمیم" | "ارزیابی" | "داده";
type QueueItem = {
  id: string;
  household: string;
  caseCode: string;
  title: string;
  detail: string;
  kind: QueueKind;
  tag: string;
  metric: string;
  time: string;
};

const queueItems: QueueItem[] = [
  {
    id: "q-1",
    household: "خانوار احمدی",
    caseCode: "هـ-۴۱۲۸",
    title: "پیگیری نتیجه ارجاع اشتغال",
    detail: "برای ارجاع ثبت‌شده هنوز نتیجه‌ای در پرونده درج نشده است.",
    kind: "ارجاع",
    tag: "پیگیری ارجاع",
    metric: "E 0.54 · 1 گلوگاه",
    time: "امروز، ۱۳:۳۰",
  },
  {
    id: "q-2",
    household: "خانوار شریفی",
    caseCode: "هـ-۳۹۸۲",
    title: "بررسی افت E و اصلاح تشخیص",
    detail: "تغییر شاخص‌ها نیازمند مرور مددکار است.",
    kind: "تصمیم",
    tag: "بررسی افت E",
    metric: "E 0.47 · PGOR 1",
    time: "امروز، ۱۴:۳۰",
  },
  {
    id: "q-3",
    household: "خانوار کاظمی",
    caseCode: "هـ-۳۷۵۴",
    title: "تأیید نسخه توانمندسازی",
    detail: "نسخهٔ پیشنهادی برای بازبینی سرپرست آماده است.",
    kind: "تصمیم",
    tag: "تأیید نسخه",
    metric: "E 0.61 · روند پایدار",
    time: "امروز، ۱۵:۰۰",
  },
  {
    id: "q-4",
    household: "خانوار بهرامی",
    caseCode: "هـ-۳۶۱۱",
    title: "تکمیل داده ارزیابی اشتغال",
    detail: "برای جمع‌بندی ارزیابی، یک منبع شواهد مشخص نشده است.",
    kind: "داده",
    tag: "کیفیت داده · نیازمند اصلاح",
    metric: "دادهٔ ناقص",
    time: "امروز، ۱۶:۰۰",
  },
  {
    id: "q-5",
    household: "خانوار اکبری",
    caseCode: "هـ-۳۴۱۷",
    title: "پیگیری نتیجه مداخله مهارت فروش",
    detail: "نتیجهٔ ثبت‌شدهٔ مداخله نیازمند مرور است.",
    kind: "ارزیابی",
    tag: "بررسی نتیجه",
    metric: "PGOR · مهارت",
    time: "امروز، ۱۷:۰۰",
  },
];

const filters = ["همه", "اقدام امروز", "نیازمند تصمیم", "ارجاعات", "ارزیابی‌ها"] as const;
type QueueFilter = typeof filters[number];

function matchesFilter(item: QueueItem, filter: QueueFilter): boolean {
  if (filter === "همه" || filter === "اقدام امروز") return true;
  if (filter === "نیازمند تصمیم") return item.kind === "تصمیم";
  if (filter === "ارجاعات") return item.kind === "ارجاع";
  return item.kind === "ارزیابی";
}

export function FigmaQueueDemo() {
  const [filter, setFilter] = useState<QueueFilter>("اقدام امروز");
  const [query, setQuery] = useState("");
  const visible = useMemo(() => queueItems.filter((item) =>
    matchesFilter(item, filter) && `${item.household} ${item.caseCode} ${item.title}`.includes(query.trim()),
  ), [filter, query]);

  return (
    <main className="fh-queue" dir="rtl" aria-label="کارتابل مددکار">
      <header className="fh-queue__top">
        <div className="fh-queue__user">
          <span className="fh-queue__avatar">م</span>
          <span><b>نام مددکار</b><small>مددکار پرونده</small></span>
          <button type="button" aria-label="تنظیمات">⚙</button>
          <button type="button" aria-label="اعلان‌ها">♧</button>
        </div>
        <div className="fh-queue__brand"><b>هامون</b><small>ماشین توانمندسازی هوشمند</small></div>
      </header>

      <section className="fh-queue__intro">
        <div>
          <div className="fh-queue__crumb">خانه <span>/</span> کارتابل</div>
          <h1>کارتابل من</h1>
          <p>اقدام‌ها، پیگیری‌ها و تصمیم‌هایی که امروز نیازمند توجه شما هستند.</p>
        </div>
        <div className="fh-queue__date">امروز، ۱۲ مهر ۱۴۰۵</div>
      </section>

      <div className="fh-queue__day-filters" role="group" aria-label="بازهٔ زمانی">
        {["همه", "این هفته", "امروز"].map((item) => <button className={item === "امروز" ? "is-active" : ""} key={item} type="button">{item}</button>)}
      </div>

      <section className="fh-queue__stats" aria-label="خلاصهٔ کارتابل">
        {[
          ["۱۲", "اقدام امروز", "cyan"],
          ["۳", "عقب‌افتاده", "gold"],
          ["۴", "نیازمند تصمیم", "blue"],
          ["۵", "ارجاع بدون پاسخ", "teal"],
          ["۶", "ارزیابی مجدد", "cyan"],
        ].map(([value, label, color]) => (
          <article className={`fh-queue__stat fh-queue__stat--${color}`} key={label}>
            <strong>{value}</strong><span>{label}</span>
          </article>
        ))}
      </section>

      <div className="fh-queue__filters">
        <label className="fh-queue__search"><span aria-hidden="true">⌕</span><input aria-label="جستجوی پرونده" placeholder="جستجوی خانوار یا کد پرونده" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <button type="button" className="fh-queue__select">همهٔ خانوارها⌄</button>
        <div className="fh-queue__tabs" role="tablist" aria-label="نوع اقدام">
          {filters.map((item) => <button aria-selected={filter === item} className={filter === item ? "is-active" : ""} key={item} onClick={() => setFilter(item)} role="tab" type="button">{item}</button>)}
        </div>
      </div>

      <div className="fh-queue__layout">
        <section className="fh-queue__main">
          <div className="fh-queue__section-title"><div><span>اقدام‌های اولویت‌دار</span><h2>نیازمند اقدام امروز</h2></div><b>{visible.length.toLocaleString("fa-IR")} مورد</b></div>
          {visible.length ? <div className="fh-queue__items">
            {visible.map((item) => (
              <article className="fh-queue__item" key={item.id}>
                <span className={`fh-queue__edge fh-queue__edge--${item.kind === "ارجاع" ? "gold" : item.kind === "تصمیم" ? "teal" : "blue"}`} />
                <div className="fh-queue__household"><b>{item.household}</b><small>مشاهده در پروندهٔ هوشمند</small><small>{item.caseCode}</small></div>
                <div className="fh-queue__task"><b>{item.title}</b><p>{item.detail}</p><span className="fh-queue__tag">{item.tag}</span></div>
                <div className="fh-queue__meta"><strong>{item.metric}</strong><small>{item.time}</small></div>
                <button className="fh-queue__action" type="button">بررسی پرونده</button>
              </article>
            ))}
          </div> : <p className="fh-queue__empty">موردی با این فیلتر پیدا نشد.</p>}
        </section>

        <aside className="fh-queue__side">
          <section className="fh-queue__side-card">
            <div className="fh-queue__section-title"><div><span>نیازمند پیگیری</span><h2>عقب‌افتاده</h2></div><b>۳ مورد</b></div>
            <article><strong>پیگیری ارجاع اشتغال</strong><small>خانوار احمدی · ۲ روز تأخیر</small></article>
            <article><strong>ارزیابی مجدد</strong><small>خانوار کریمی · ۵ روز تأخیر</small></article>
            <button type="button">دیدن همهٔ موارد ←</button>
          </section>
          <section className="fh-queue__spotlight">
            <span>پیشنهاد هامون</span><h2>خانوار رضایی</h2><strong>بازبینی مسیر توانمندسازی</strong>
            <p>بررسی داده‌های ثبت‌شده پیش از تصمیم بعدی کمک می‌کند مسیر خانوار دقیق‌تر مرور شود.</p>
            <button type="button">بررسی پرونده</button>
          </section>
          <section className="fh-queue__side-card">
            <div className="fh-queue__section-title"><div><span>در انتظار پاسخ</span><h2>ارجاعات فعال</h2></div><b>۵ مورد</b></div>
            <article><strong>خدمت اشتغال</strong><small>خانوار محمدی · ارسال ۳ روز پیش</small></article>
            <button type="button">پیگیری ارجاعات ←</button>
          </section>
        </aside>
      </div>

      <footer className="fh-queue__footer">دموی نمایشی هامون · پرونده‌ها و اعداد این صفحه ساختگی‌اند؛ اطلاعات واقعی وارد نکنید.</footer>
    </main>
  );
}
