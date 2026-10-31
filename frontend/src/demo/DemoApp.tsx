import { useMemo, useState, type FormEvent } from "react";

import { Badge, MetricCard, Panel } from "../design-system/components";
import "./demo.css";

type DemoPage = "home" | "queue" | "households" | "detail";

type DemoHousehold = {
  id: string;
  code: string;
  status: string;
  e: number;
  p: number;
  g: number;
  o: number;
  r: number;
  bottleneck: string;
  intervention: string;
  nextAction: string;
};

type DemoWorkItem = {
  id: string;
  caseCode: string;
  title: string;
  type: string;
  reason: string;
  due: string;
  priority: "زیاد" | "متوسط" | "عادی";
  status: "باز" | "در حال رسیدگی";
};

const households: DemoHousehold[] = [
  { id: "case-1", code: "HM-1405-021", status: "فعال", e: 67.4, p: 72, g: 61, o: 58, r: 78, bottleneck: "فرصت", intervention: "آموزش مهارت", nextAction: "بازبینی نتیجه دوره مهارتی" },
  { id: "case-2", code: "HM-1405-018", status: "فعال", e: 54.8, p: 63, g: 52, o: 45, r: 69, bottleneck: "فرصت", intervention: "اتصال به بازار", nextAction: "پیگیری ارجاع شغلی" },
  { id: "case-3", code: "HM-1405-014", status: "در حال بررسی", e: 48.2, p: 55, g: 49, o: 42, r: 61, bottleneck: "ظرفیت رشد", intervention: "مشاوره و مربی‌گری", nextAction: "تکمیل ارزیابی خانوار" },
  { id: "case-4", code: "HM-1405-009", status: "فعال", e: 73.1, p: 81, g: 69, o: 66, r: 76, bottleneck: "فرصت", intervention: "تسهیل دسترسی به بازار", nextAction: "ثبت نتیجه مداخله" },
];

const workItems: DemoWorkItem[] = [
  { id: "task-1", caseCode: "HM-1405-021", title: "بازبینی نتیجه دوره مهارتی", type: "بازبینی نتیجه", reason: "موعد ارزیابی پس از پایان دوره فرا رسیده است.", due: "امروز", priority: "زیاد", status: "باز" },
  { id: "task-2", caseCode: "HM-1405-018", title: "پیگیری ارجاع شغلی", type: "پیگیری ارجاع", reason: "برای تکمیل مسیر ارجاع، نتیجه ارائه‌دهنده بررسی شود.", due: "فردا", priority: "متوسط", status: "باز" },
  { id: "task-3", caseCode: "HM-1405-014", title: "تکمیل ارزیابی خانوار", type: "تکمیل داده", reason: "چند ورودی ارزیابی در پرونده نمونه نیازمند تکمیل است.", due: "۲ روز دیگر", priority: "عادی", status: "در حال رسیدگی" },
  { id: "task-4", caseCode: "HM-1405-009", title: "ثبت نتیجه مداخله", type: "ثبت نتیجه", reason: "نتیجه اقدام برای ادامه مسیر نمایش داده می‌شود.", due: "۴ روز دیگر", priority: "متوسط", status: "باز" },
];

const number = (value: number) => value.toLocaleString("fa-IR", { maximumFractionDigits: 1 });
const selectedStatusTone = (status: string): "success" | "warning" => status === "فعال" ? "success" : "warning";

export function DemoApp() {
  const [page, setPage] = useState<DemoPage>("home");
  const [selectedId, setSelectedId] = useState("case-1");
  const [query, setQuery] = useState("");
  const selectedCase = households.find((item) => item.id === selectedId) ?? households[0];
  const filteredHouseholds = useMemo(
    () => households.filter((item) => item.code.toLocaleLowerCase("fa-IR").includes(query.trim().toLocaleLowerCase("fa-IR"))),
    [query],
  );

  function openHousehold(id: string) {
    setSelectedId(id);
    setPage("detail");
  }

  function searchHouseholds(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage("households");
  }

  return (
    <div className="demo-shell">
      <header className="demo-topbar">
        <div className="demo-topbar__inner">
          <div className="demo-user">
            <span className="demo-avatar" aria-hidden="true">م</span>
            <span><strong>نمایش سازمانی</strong><small>نسخه‌ی نمایشی</small></span>
          </div>
          <div className="demo-brand" aria-label="هامون">
            <span><strong>هامون</strong><small>ماشین توانمندسازی هوشمند</small></span>
            <span className="demo-brand__mark" aria-hidden="true"><i /><i /><i /></span>
          </div>
        </div>
        <nav className="demo-nav" aria-label="ناوبری دمو">
          {([
            ["home", "خانه"],
            ["queue", "کارتابل"],
            ["households", "پرونده‌ها"],
          ] as const).map(([value, label]) => (
            <button
              className={page === value ? "demo-nav__item is-active" : "demo-nav__item"}
              key={value}
              onClick={() => setPage(value)}
              type="button"
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      <div className="demo-notice" role="status">
        <span className="demo-notice__dot" />
        <strong>دموی نمایشی هامون</strong>
        <span>همه‌ی پرونده‌ها و اعداد این صفحه فرضی‌اند؛ اطلاعاتی ذخیره یا به سامانه‌ای ارسال نمی‌شود.</span>
        <Badge tone="warning">فقط نمایش</Badge>
      </div>

      <main className="demo-main">
        {page === "home" ? (
          <div className="page-stack">
            <header className="page-heading">
              <div>
                <span className="eyebrow">مدیریت مسیر توانمندسازی</span>
                <h1>داشبورد هامون</h1>
                <p>نمایی یکپارچه از پرونده‌ها، شاخص‌ها و اقدام‌های پیش رو</p>
              </div>
              <Badge tone="accent">داده‌ی نمونه</Badge>
            </header>

            <section className="demo-hero">
              <div className="demo-hero__copy">
                <Badge tone="accent">مدل مسیر توانمندسازی</Badge>
                <h2>از شناخت وضعیت تا ساختن مسیر رشد</h2>
                <p>نمایش پرونده، شاخص‌های PGOR و اقدام‌های پیگیری در یک فضای کاری واحد.</p>
                <form className="demo-search" onSubmit={searchHouseholds}>
                  <label className="sr-only" htmlFor="demo-case-search">جست‌وجوی کد پرونده</label>
                  <input id="demo-case-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جست‌وجو با کد پرونده‌ی نمونه" />
                  <button className="hm-button hm-button--primary" type="submit">جست‌وجو</button>
                </form>
                <div className="demo-stage-row"><span>تشخیص</span><i /><span>اقدام</span><i /><span>سنجش</span><i /><span>یادگیری</span></div>
              </div>
              <div className="demo-journey" aria-hidden="true">
                <div className="demo-journey__orb"><span /><span /><span /><b>مسیر<br />توانمندی</b></div>
                <div className="demo-journey__labels"><span>استقلال پایدار</span><span>آستانه توانمندی</span><span>توانمندسازی</span><span>حمایت هدفمند</span></div>
              </div>
            </section>

            <section className="demo-metrics" aria-label="شاخص‌های نمایشی">
              <MetricCard label="پرونده‌های نمونه" value={households.length} hint="در محیط نمایشی" />
              <MetricCard label="دارای شاخص PGOR" value={households.length} hint="مقادیر صرفاً نمونه‌اند" />
              <MetricCard label="مداخله‌ی جاری" value={households.length} hint="نمایش مسیرهای فرضی" />
              <MetricCard label="اقدام‌های امروز" value="۱" hint="در کارتابل نمونه" />
            </section>

            <section className="demo-home-grid">
              <Panel className="demo-summary-panel">
                <div className="section-heading"><div><span className="eyebrow">نمای کلی</span><h2>تصویر کلی مسیرها</h2></div><Badge tone="success">نمایشی</Badge></div>
                <div className="demo-summary-stat"><strong>۴</strong><span>پرونده در محیط نمونه</span></div>
                <div className="demo-summary-stat"><strong>۳</strong><span>اقدام باز برای نمایش</span></div>
                <button className="demo-text-button" onClick={() => setPage("households")} type="button">رفتن به فهرست پرونده‌ها ←</button>
              </Panel>
              <Panel className="demo-table-panel">
                <div className="section-heading"><div><span className="eyebrow">پرونده‌های اخیر</span><h2>مسیرهای در حال پیگیری</h2></div><button className="demo-text-button" onClick={() => setPage("households")} type="button">مشاهده همه ←</button></div>
                <div className="demo-table">
                  <div className="demo-table__row demo-table__row--head"><span>کد پرونده</span><span>شاخص E</span><span>وضعیت</span><span>اقدام بعدی</span></div>
                  {households.slice(0, 3).map((item) => (
                    <button className="demo-table__row" key={item.id} onClick={() => openHousehold(item.id)} type="button">
                      <strong>{item.code}</strong><strong>{number(item.e)}</strong><Badge tone={selectedStatusTone(item.status)}>{item.status}</Badge><span>{item.nextAction}</span>
                    </button>
                  ))}
                </div>
              </Panel>
            </section>
          </div>
        ) : null}

        {page === "queue" ? (
          <div className="page-stack">
            <header className="page-heading">
              <div><span className="eyebrow">اقدام‌ها و پیگیری‌های ارجاع‌شده</span><h1>کارتابل</h1><p>نمایش نمونه‌ی صف اقدام‌های مددکار</p></div>
              <Badge tone="accent">۴ مورد نمونه</Badge>
            </header>
            <section className="demo-metrics">
              <MetricCard label="اقدام امروز" value="۱" /><MetricCard label="عقب‌افتاده" value="۰" /><MetricCard label="نیازمند اقدام" value="۳" /><MetricCard label="در حال رسیدگی" value="۱" />
            </section>
            <div className="demo-queue-layout">
              <div className="page-stack">
                <Panel>
                  <div className="section-heading"><div><span className="eyebrow">بر اساس موعد و اولویت</span><h2>نیازمند اقدام</h2></div><Badge tone="accent">۳ مورد</Badge></div>
                  <div className="demo-work-list">{workItems.filter((item) => item.status === "باز").map((item) => <WorkRow key={item.id} item={item} onOpen={() => openHousehold(households.find((caseItem) => caseItem.code === item.caseCode)?.id ?? "case-1")} />)}</div>
                </Panel>
                <Panel>
                  <div className="section-heading"><div><span className="eyebrow">وضعیت فعلی</span><h2>در حال رسیدگی</h2></div><Badge tone="neutral">۱ مورد</Badge></div>
                  <div className="demo-work-list">{workItems.filter((item) => item.status === "در حال رسیدگی").map((item) => <WorkRow key={item.id} item={item} onOpen={() => openHousehold("case-3")} />)}</div>
                </Panel>
              </div>
              <aside className="demo-queue-aside">
                <Panel><div className="section-heading"><h2>عقب‌افتاده</h2><Badge tone="success">۰</Badge></div><p className="demo-muted">در این مجموعه‌ی نمایشی اقدام عقب‌افتاده‌ای وجود ندارد.</p></Panel>
                <Panel><div className="section-heading"><h2>پیش رو</h2><Badge tone="accent">۳</Badge></div><ul className="demo-upcoming"><li><strong>پیگیری ارجاع شغلی</strong><span>فردا · HM-1405-018</span></li><li><strong>تکمیل ارزیابی خانوار</strong><span>۲ روز دیگر · HM-1405-014</span></li><li><strong>ثبت نتیجه مداخله</strong><span>۴ روز دیگر · HM-1405-009</span></li></ul></Panel>
              </aside>
            </div>
          </div>
        ) : null}

        {page === "households" ? (
          <div className="page-stack">
            <header className="page-heading">
              <div><span className="eyebrow">مجموعه‌ی کاملاً فرضی</span><h1>پرونده‌های خانوار</h1><p>برای مشاهده‌ی جزئیات نمایشی، یک ردیف را انتخاب کنید.</p></div>
              <Badge tone="warning">دمو · بدون داده‌ی واقعی</Badge>
            </header>
            <Panel className="demo-household-list">
              <form className="demo-search demo-search--compact" onSubmit={(event) => event.preventDefault()}>
                <label className="sr-only" htmlFor="demo-list-search">جست‌وجو</label>
                <input id="demo-list-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="جست‌وجو با کد پرونده" />
                <span>{filteredHouseholds.length.toLocaleString("fa-IR")} پرونده</span>
              </form>
              <div className="demo-case-rows">
                {filteredHouseholds.map((item) => (
                  <button className="demo-case-row" key={item.id} onClick={() => openHousehold(item.id)} type="button">
                    <span className="demo-case-row__code"><strong>{item.code}</strong><small>پرونده‌ی نمایشی</small></span>
                    <span><small>شاخص نمونه E</small><strong>{number(item.e)}</strong></span>
                    <span><small>گلوگاه نمونه</small><strong>{item.bottleneck}</strong></span>
                    <span><small>مداخله‌ی نمونه</small><strong>{item.intervention}</strong></span>
                    <span><Badge tone={selectedStatusTone(item.status)}>{item.status}</Badge></span>
                    <span className="demo-case-row__arrow">←</span>
                  </button>
                ))}
                {filteredHouseholds.length === 0 ? <p className="demo-muted">پرونده‌ی نمونه‌ای با این کد پیدا نشد.</p> : null}
              </div>
            </Panel>
          </div>
        ) : null}

        {page === "detail" ? (
          <div className="page-stack">
            <button className="demo-back" onClick={() => setPage("households")} type="button">← بازگشت به پرونده‌ها</button>
            <header className="page-heading">
              <div><span className="eyebrow">نمای جزئیات · اطلاعات فرضی</span><h1>پرونده {selectedCase.code}</h1><p>این صفحه برای نمایش ساختار محصول است و به پرونده‌ی واقعی متصل نیست.</p></div>
              <Badge tone={selectedStatusTone(selectedCase.status)}>{selectedCase.status}</Badge>
            </header>
            <section className="demo-detail-grid">
              <Panel className="demo-pgor-panel">
                <div className="section-heading"><div><span className="eyebrow">شاخص نمایشی</span><h2>وضعیت PGOR</h2></div><Badge tone="accent">مقدار ساختگی</Badge></div>
                <div className="demo-e-score"><span>شاخص توانمندسازی E</span><strong>{number(selectedCase.e)}</strong><small>داده‌ی نمونه برای نمایش رابط کاربری</small></div>
                <div className="demo-pgor-grid">{([["P", selectedCase.p, "مشارکت"], ["G", selectedCase.g, "ظرفیت رشد"], ["O", selectedCase.o, "فرصت"], ["R", selectedCase.r, "تاب‌آوری"]] as const).map(([code, value, label]) => <div className="demo-pgor-item" key={code}><span>{label}</span><strong>{code} {number(value)}</strong></div>)}</div>
                <div className="demo-fake-note">این امتیازها محاسبه‌ی رسمی هامون نیستند.</div>
              </Panel>
              <div className="page-stack">
                <Panel><div className="section-heading"><div><span className="eyebrow">مسیر نمایشی</span><h2>مداخله‌ی جاری</h2></div><Badge tone="success">فعال · نمونه</Badge></div><div className="demo-detail-card"><strong>{selectedCase.intervention}</strong><span>هدف فرضی: {selectedCase.bottleneck}</span></div></Panel>
                <Panel><div className="section-heading"><div><span className="eyebrow">کارتابل پرونده</span><h2>اقدام بعدی</h2></div><Badge tone="warning">نمایشی</Badge></div><div className="demo-detail-card"><strong>{selectedCase.nextAction}</strong><span>موعد نمونه: در چند روز آینده</span></div></Panel>
                <Panel><div className="section-heading"><div><span className="eyebrow">رد زمانی نمونه</span><h2>آخرین رویدادها</h2></div></div><div className="demo-timeline"><span><i />ارزیابی نمونه نمایش داده شد</span><span><i />مسیر مداخله‌ی فرضی آماده است</span><span><i />اقدام نمایشی به کارتابل افزوده شد</span></div></Panel>
              </div>
            </section>
          </div>
        ) : null}
      </main>
      <footer className="demo-footer"><span>هامون · محیط نمایشی</span><span>اطلاعات این نسخه ساختگی و غیرقابل استناد است.</span></footer>
    </div>
  );
}

function WorkRow({ item, onOpen }: { item: DemoWorkItem; onOpen: () => void }) {
  return (
    <article className="demo-work-row">
      <div className="demo-work-row__top"><Badge tone={item.priority === "زیاد" ? "danger" : item.priority === "متوسط" ? "warning" : "neutral"}>اولویت {item.priority}</Badge><Badge tone="accent">{item.type}</Badge></div>
      <button className="demo-work-row__title" onClick={onOpen} type="button">{item.title}<span>پرونده {item.caseCode} ←</span></button>
      <p>{item.reason}</p>
      <div className="demo-work-row__bottom"><span>موعد نمونه: {item.due}</span><span>{item.status}</span></div>
    </article>
  );
}
