import { useMemo, useState } from "react";
import "./figma-households-demo.css";

type HouseholdRow = {
  name: string; code: string; score: string; stage: string; group: string;
  updated: string; intervention: string; nextAction: string; status: string; trend: "up" | "flat" | "down";
};
const households: HouseholdRow[] = [
  { name: "خانوار احمدی", code: "H-1405-21842", score: "0.54", stage: "توانمندسازی حمایتی", group: "فرصت", updated: "۱۲ مهر", intervention: "اشتغال · در حال اجرا", nextAction: "پیگیری ارجاع اشتغال", status: "ارجاع بدون پاسخ", trend: "up" },
  { name: "خانوار شریفی", code: "H-1405-39281", score: "0.47", stage: "توانمندسازی حمایتی", group: "تاب‌آوری", updated: "۱۰ مهر", intervention: "مشاوره · فعال", nextAction: "بررسی افت شاخص E", status: "افت E", trend: "down" },
  { name: "خانوار کریمی", code: "H-1405-36110", score: "0.39", stage: "آسیب‌پذیر", group: "تاب‌آوری", updated: "۲ مهر", intervention: "حمایت روانی · فعال", nextAction: "ارزیابی مجدد خانوار", status: "زیر آستانه", trend: "down" },
  { name: "خانوار کاظمی", code: "H-1405-44502", score: "0.71", stage: "آستانه توانمندی", group: "ظرفیت رشد", updated: "۱۱ مهر", intervention: "مهارت فروش · در حال اجرا", nextAction: "تأیید نسخهٔ جدید", status: "نیازمند تصمیم", trend: "up" },
  { name: "خانوار نادری", code: "H-1405-28640", score: "0.58", stage: "توانمندسازی حمایتی", group: "مشارکت", updated: "۱۲ مهر", intervention: "بدون مداخلهٔ فعال", nextAction: "—", status: "بدون اقدام بعدی", trend: "flat" },
  { name: "خانوار محمدی", code: "H-1405-37562", score: "0.42", stage: "آسیب‌پذیر", group: "فرصت", updated: "۲۷ شهریور", intervention: "اشتغال · ارجاع‌شده", nextAction: "تکمیل ارزیابی", status: "ارزیابی نیمه‌تمام", trend: "down" },
];

const filters = ["همه", "نیازمند توجه", "روند نزولی", "زیر آستانه", "مداخله فعال", "نیازمند ارزیابی", "بدون اقدام بعدی"] as const;
type Filter = typeof filters[number];

function visibleWithFilter(row: HouseholdRow, filter: Filter): boolean {
  if (filter === "همه") return true;
  if (filter === "نیازمند توجه") return row.status !== "بدون اقدام بعدی";
  if (filter === "روند نزولی") return row.trend === "down";
  if (filter === "زیر آستانه") return row.status === "زیر آستانه";
  if (filter === "مداخله فعال") return row.intervention.includes("فعال") || row.intervention.includes("اجرا");
  if (filter === "نیازمند ارزیابی") return row.status === "ارزیابی نیمه‌تمام";
  return row.status === "بدون اقدام بعدی";
}

export function FigmaHouseholdsDemo() {
  const [filter, setFilter] = useState<Filter>("همه");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const visible = useMemo(() => households.filter((row) =>
    visibleWithFilter(row, filter) && `${row.name} ${row.code} ${row.nextAction}`.includes(query.trim()),
  ), [filter, query]);

  return (
    <main className="fh-households" dir="rtl" aria-label="فهرست پرونده‌های مددکار">
      <header className="fh-households__header">
        <div><div className="fh-households__crumb">خانه <span>/</span> پرونده‌های من</div><h1>پرونده‌های من</h1><p>خانوارهای تحت مسئولیت شما و آخرین وضعیت مسیر توانمندسازی آن‌ها</p></div>
        <div className="fh-households__badges"><span><b>۱۲۸</b> خانوار فعال</span><span className="is-attention"><b>۸</b> پرونده نیازمند توجه</span></div>
      </header>

      <label className="fh-households__search"><span aria-hidden="true">⌕</span><input aria-label="جستجوی خانوار" placeholder="جستجوی نام خانوار، کد ملی یا کد پرونده" value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>Ctrl K</kbd></label>

      <div className="fh-households__filters" role="tablist" aria-label="فیلتر پرونده‌ها">
        {filters.map((item) => <button aria-selected={filter === item} className={filter === item ? "is-active" : ""} key={item} onClick={() => setFilter(item)} role="tab" type="button">{item}</button>)}
      </div>

      <section className="fh-households__distribution" aria-label="نمای جمعیت در مسیر توانمندسازی">
        <div className="fh-households__distribution-head"><strong>نمای جمعیت در مسیر توانمندسازی</strong><span>انتخاب هر گروه، فهرست را فیلتر می‌کند</span></div>
        <div className="fh-households__bands">
          {[
            ["استقلال پایدار", "۱۲", "۰٫۸۸", "بدون گلوگاه", "stable"],
            ["آستانه توانمندی", "۲۴", "۰٫۷۳", "۱ اولویت فعال", "threshold"],
            ["توانمندسازی حمایتی", "۵۲", "۰٫۵۴", "۳ اولویت جاری", "support"],
            ["آسیب‌پذیر", "۳۱", "۰٫۳۶", "۲ اولویت جاری", "vulnerable"],
            ["وابستگی شدید", "۹", "۰٫۲۱", "۳ اولویت توجه", "critical"],
          ].map(([label, count, score, note, tone]) => <article className={`fh-households__band fh-households__band--${tone}`} key={label}><small>{count} خانوار</small><b>{label}</b><strong>E {score}</strong><span>{note}</span></article>)}
        </div>
      </section>

      <section className="fh-households__table-card">
        <header className="fh-households__table-head"><div><h2>همهٔ خانوارها</h2><small>نمایش {visible.length ? 1 : 0} تا {visible.length} از ۱۲۸</small></div><button onClick={() => setNotice("خروجی این فهرست در نسخهٔ نمایشی ساخته نمی‌شود.")} type="button">خروجی فهرست</button></header>
        <div className="fh-households__table-wrap">
          <table>
            <thead><tr><th>نام خانوار</th><th>کد پرونده</th><th>مرحلهٔ فعلی</th><th>روند E</th><th>گلوگاه اصلی</th><th>آخرین ارزیابی</th><th>مداخلهٔ فعال</th><th>اقدام بعدی</th><th>وضعیت توجه</th></tr></thead>
            <tbody>
              {visible.map((row) => <tr key={row.code}>
                <td><b>{row.name}</b><small>باز کردن پروندهٔ هوشمند</small></td><td dir="ltr">{row.code}</td><td>{row.stage}</td>
                <td><strong>E {row.score}</strong><small className={`fh-households__trend fh-households__trend--${row.trend}`}>{row.trend === "up" ? "↑ روند رشد" : row.trend === "down" ? "↓ روند نزولی" : "→ پایدار"}</small></td>
                <td><span className="fh-households__group">{row.group}</span></td><td>{row.updated}</td><td>{row.intervention}</td><td><b>{row.nextAction}</b></td><td><span className="fh-households__status">{row.status}</span></td>
              </tr>)}
            </tbody>
          </table>
          {visible.length === 0 ? <p className="fh-households__empty">پرونده‌ای با این جست‌وجو یا فیلتر پیدا نشد.</p> : null}
        </div>
        <footer className="fh-households__pagination"><span>نمایش ۱ تا {visible.length} پرونده</span><div><button type="button">قبلی</button><button className="is-active" type="button">۱</button><button type="button">۲</button><button type="button">۳</button><button type="button">بعدی</button></div></footer>
      </section>
      {notice ? <p className="fh-households__notice" role="status">{notice}</p> : null}
      <footer className="fh-households__footer">دموی نمایشی هامون · اعداد و پرونده‌ها نمونه‌اند و برای ثبت اطلاعات واقعی نیستند.</footer>
    </main>
  );
}
