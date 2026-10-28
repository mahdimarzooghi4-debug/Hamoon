import { useEffect, useMemo, useState, type FormEvent } from "react";

type Group = "P" | "G" | "O" | "R";
type ResponseType = "text" | "number" | "yes_no" | "choice";
type Question = {
  id: string;
  group: Group;
  groupName: string;
  category: string;
  prompt: string;
  responseType: ResponseType;
  options: string;
  active: boolean;
  draft: boolean;
};

const groups: { id: Group; name: string }[] = [
  { id: "P", name: "مشارکت" },
  { id: "G", name: "ظرفیت رشد" },
  { id: "O", name: "فرصت" },
  { id: "R", name: "تاب‌آوری" },
];

const seeds: Omit<Question, "active" | "draft" | "responseType" | "options">[] = [
  { id: "p-motivation", group: "P", groupName: "مشارکت", category: "انگیزه", prompt: "در حال حاضر چه تغییر یا هدفی را برای بهبود شرایط خانواده دنبال می‌کنید؟" },
  { id: "p-hope", group: "P", groupName: "مشارکت", category: "امید به آینده", prompt: "خانواده برای شش ماه آینده چه برنامه‌ای دارد؟" },
  { id: "p-responsibility", group: "P", groupName: "مشارکت", category: "مسئولیت‌پذیری", prompt: "در پیگیری کارهای توافق‌شده، چه اقدام‌هایی انجام شده است؟" },
  { id: "p-commitments", group: "P", groupName: "مشارکت", category: "انجام تعهدات", prompt: "کدام تعهدهای توافق‌شده انجام شده یا هنوز نیاز به پیگیری دارد؟" },
  { id: "p-interaction", group: "P", groupName: "مشارکت", category: "تعامل", prompt: "خانواده برای دریافت خدمات با کدام نهادها یا افراد در ارتباط است؟" },
  { id: "p-social", group: "P", groupName: "مشارکت", category: "مشارکت اجتماعی", prompt: "خانواده در چه فعالیت‌های اجتماعی یا محلی شرکت می‌کند؟" },
  { id: "p-programs", group: "P", groupName: "مشارکت", category: "حضور در برنامه‌ها", prompt: "در دوره اخیر، خانواده در کدام برنامه‌ها یا جلسات شرکت کرده است؟" },
  { id: "g-education", group: "G", groupName: "ظرفیت رشد", category: "تحصیلات", prompt: "بالاترین سطح تحصیلات هر یک از اعضای بزرگسال خانواده چیست؟" },
  { id: "g-skills", group: "G", groupName: "ظرفیت رشد", category: "مهارت", prompt: "اعضای خانواده چه مهارت‌هایی دارند یا مایل‌اند یاد بگیرند؟" },
  { id: "g-work", group: "G", groupName: "ظرفیت رشد", category: "سابقه کاری", prompt: "اعضای خانواده چه تجربه‌های کاری داشته‌اند؟" },
  { id: "g-production", group: "G", groupName: "ظرفیت رشد", category: "تجربه تولید", prompt: "آیا خانواده تجربه تولید یا عرضه محصول و خدمت دارد؟ شرح دهید." },
  { id: "g-learning", group: "G", groupName: "ظرفیت رشد", category: "قابلیت یادگیری", prompt: "خانواده برای یادگیری مهارت تازه به چه آموزش یا پشتیبانی‌ای نیاز دارد؟" },
  { id: "g-flexibility", group: "G", groupName: "ظرفیت رشد", category: "انعطاف‌پذیری", prompt: "وقتی برنامه‌ای طبق انتظار پیش نمی‌رود، خانواده معمولاً چه تغییری در برنامه می‌دهد؟" },
  { id: "g-health", group: "G", groupName: "ظرفیت رشد", category: "سلامت عملکردی", prompt: "آیا محدودیتی وجود دارد که بر انجام کارهای روزمره یا فعالیت شغلی اثر بگذارد؟ (اختیاری)" },
  { id: "o-market", group: "O", groupName: "فرصت", category: "بازار", prompt: "در محل زندگی خانواده چه فرصت‌های شغلی یا تقاضایی برای محصولات و خدمات وجود دارد؟" },
  { id: "o-infrastructure", group: "O", groupName: "فرصت", category: "زیرساخت", prompt: "دسترسی خانواده به حمل‌ونقل و اینترنت برای کار یا آموزش چگونه است؟" },
  { id: "o-services", group: "O", groupName: "فرصت", category: "دسترسی به خدمات", prompt: "برای استفاده از خدمات موردنیاز، خانواده با چه مانع یا کمبودی روبه‌رو است؟" },
  { id: "o-capital", group: "O", groupName: "فرصت", category: "دسترسی به سرمایه", prompt: "برای شروع یا گسترش فعالیت اقتصادی، خانواده چه منابع مالی یا حمایتی در دسترس دارد؟" },
  { id: "o-network", group: "O", groupName: "فرصت", category: "شبکه اقتصادی", prompt: "خانواده با چه خریداران، تأمین‌کنندگان یا فعالان اقتصادی ارتباط دارد؟" },
  { id: "r-income", group: "R", groupName: "تاب‌آوری", category: "ثبات درآمد", prompt: "درآمد خانواده در ماه‌های اخیر تا چه اندازه منظم و قابل پیش‌بینی بوده است؟" },
  { id: "r-support", group: "R", groupName: "تاب‌آوری", category: "حمایت اجتماعی", prompt: "در زمان نیاز، خانواده از چه افراد یا نهادهایی می‌تواند کمک بگیرد؟" },
  { id: "r-health", group: "R", groupName: "تاب‌آوری", category: "سلامت خانوادگی", prompt: "آیا نیاز سلامتِ تأمین‌نشده‌ای هست که خانواده بخواهد برای دسترسی به خدمات پیگیری کند؟ (اختیاری)" },
  { id: "r-crisis", group: "R", groupName: "تاب‌آوری", category: "مقابله با بحران", prompt: "در مواجهه با یک هزینه یا بحران پیش‌بینی‌نشده، خانواده معمولاً از چه راه‌هایی کمک می‌گیرد؟" },
  { id: "r-diversity", group: "R", groupName: "تاب‌آوری", category: "تنوع منابع درآمدی", prompt: "منابع درآمدی خانواده چیست و آیا بیش از یک منبع درآمد دارد؟" },
];

const initialQuestions: Question[] = seeds.map((item) => ({
  ...item,
  responseType: "text",
  options: "",
  active: true,
  draft: true,
}));

const storageKey = "hamoon-demo-question-bank-v1";

function loadQuestions(): Question[] {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw) {
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed)) return parsed as Question[];
    }
  } catch {
    // Fall back to the draft catalog if local browser storage is unavailable.
  }
  return initialQuestions;
}

const responseLabels: Record<ResponseType, string> = {
  text: "پاسخ متنی",
  number: "عدد",
  yes_no: "بله / خیر",
  choice: "گزینه‌ای",
};

export function FigmaQuestionBankAdminDemo() {
  const [questions, setQuestions] = useState<Question[]>(loadQuestions);
  const [filter, setFilter] = useState<Group | "ALL">("ALL");
  const [editing, setEditing] = useState<Question | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(questions));
  }, [questions]);

  const visible = useMemo(
    () => questions.filter((question) => filter === "ALL" || question.group === filter),
    [filter, questions],
  );

  function saveQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || !editing.prompt.trim() || !editing.category.trim()) return;
    setQuestions((current) => {
      const exists = current.some((item) => item.id === editing.id);
      return exists
        ? current.map((item) => item.id === editing.id ? { ...editing, prompt: editing.prompt.trim() } : item)
        : [{ ...editing, prompt: editing.prompt.trim() }, ...current];
    });
    setNotice("پرسش در پیش‌نویس همین مرورگر ذخیره شد.");
    setEditing(null);
  }

  function addQuestion() {
    const group = filter === "ALL" ? "P" : filter;
    const groupName = groups.find((item) => item.id === group)!.name;
    setEditing({
      id: `custom-${Date.now()}`, group, groupName, category: "", prompt: "",
      responseType: "text", options: "", active: true, draft: true,
    });
  }

  function toggleActive(question: Question) {
    setQuestions((current) => current.map((item) =>
      item.id === question.id ? { ...item, active: !item.active } : item,
    ));
    setNotice(question.active
      ? "پرسش از فرم فعال خارج شد؛ سابقه آن در پیش‌نویس باقی ماند."
      : "پرسش دوباره در فهرست فعال قرار گرفت.");
  }

  return (
    <main className="fh-question-admin" dir="rtl" aria-label="مدیریت پرسش‌های هامون">
      <header className="fh-question-admin__header">
        <div>
          <span className="fh-intake__eyebrow">پنل مدیریت · نسخهٔ نمایشی</span>
          <h1>بانک پرسش‌های مدل PGOR</h1>
          <p>پرسش‌ها زیر شاخص‌های مدل دسته‌بندی می‌شوند. این متن‌ها پیش‌نویس‌اند و پیش از استفاده میدانی باید تأیید شوند.</p>
        </div>
        <button className="fh-question-admin__add" onClick={addQuestion} type="button">＋ افزودن پرسش</button>
      </header>

      <div className="fh-question-admin__notice" role="note">
        امتیازدهی و نگاشت پاسخ به امتیاز هنوز در سند مدل مشخص نشده است. نوع پاسخ را می‌توانید برای طراحی فرم تعیین کنید؛ امتیاز رسمی تولید نمی‌شود.
      </div>

      <div className="fh-question-admin__tabs" role="tablist" aria-label="دسته‌های PGOR">
        <button className={filter === "ALL" ? "is-active" : ""} onClick={() => setFilter("ALL")} type="button">همهٔ دسته‌ها <span>{questions.length}</span></button>
        {groups.map((group) => (
          <button className={filter === group.id ? "is-active" : ""} key={group.id} onClick={() => setFilter(group.id)} type="button">
            {group.id} · {group.name} <span>{questions.filter((item) => item.group === group.id).length}</span>
          </button>
        ))}
      </div>

      {notice ? <p className="fh-question-admin__toast" role="status">{notice}</p> : null}

      {editing ? (
        <form className="fh-question-admin__editor" onSubmit={saveQuestion}>
          <div className="fh-question-admin__editor-head">
            <div><small>{editing.id.startsWith("custom-") ? "پرسش تازه" : "ویرایش پرسش"}</small><h2>مشخصات پرسش</h2></div>
            <button aria-label="بستن فرم" onClick={() => setEditing(null)} type="button">×</button>
          </div>
          <div className="fh-question-admin__fields">
            <label>دستهٔ مدل
              <select value={editing.group} onChange={(event) => {
                const group = event.target.value as Group;
                setEditing({ ...editing, group, groupName: groups.find((item) => item.id === group)!.name });
              }}>{groups.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}</select>
            </label>
            <label>شاخص / موضوع
              <input required value={editing.category} onChange={(event) => setEditing({ ...editing, category: event.target.value })} placeholder="مثلاً ثبات درآمد" />
            </label>
            <label className="is-wide">متن پرسش
              <textarea required rows={3} value={editing.prompt} onChange={(event) => setEditing({ ...editing, prompt: event.target.value })} placeholder="پرسش روشن و قابل پاسخ برای مددکار بنویسید" />
            </label>
            <label>نوع پاسخ
              <select value={editing.responseType} onChange={(event) => setEditing({ ...editing, responseType: event.target.value as ResponseType })}>
                {Object.entries(responseLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            {editing.responseType === "choice" ? <label>گزینه‌های پاسخ
              <input value={editing.options} onChange={(event) => setEditing({ ...editing, options: event.target.value })} placeholder="هر گزینه را با ویرگول جدا کنید" />
            </label> : null}
          </div>
          <div className="fh-question-admin__editor-actions">
            <button className="fh-question-admin__add" type="submit">ذخیرهٔ پیش‌نویس</button>
            <button className="fh-question-admin__cancel" onClick={() => setEditing(null)} type="button">انصراف</button>
          </div>
        </form>
      ) : null}

      <section className="fh-question-admin__list" aria-label="فهرست پرسش‌ها">
        {visible.map((question, index) => (
          <article className={`fh-question-admin__item ${question.active ? "" : "is-inactive"}`} key={question.id}>
            <div className="fh-question-admin__index">{String(index + 1).padStart(2, "0")}</div>
            <div className="fh-question-admin__copy">
              <div className="fh-question-admin__meta"><span>{question.group} · {question.groupName}</span><b>{question.category}</b></div>
              <p>{question.prompt}</p>
              <small>{responseLabels[question.responseType]}{question.options ? ` · ${question.options}` : ""} · {question.draft ? "پیش‌نویس برای بازبینی" : "تنظیم‌شده"}</small>
            </div>
            <div className="fh-question-admin__actions">
              <button onClick={() => setEditing(question)} type="button">ویرایش</button>
              <button className={question.active ? "is-danger" : ""} onClick={() => toggleActive(question)} type="button">{question.active ? "خروج از فرم" : "فعال‌سازی"}</button>
            </div>
          </article>
        ))}
        {visible.length === 0 ? <p className="fh-question-admin__empty">هنوز پرسشی ثبت نشده است.</p> : null}
      </section>
      <footer className="fh-question-admin__footer">تغییرات این دمو در حافظهٔ مرورگر ذخیره می‌شوند؛ برای استفادهٔ واقعی باید API و ذخیره‌سازی سمت سرور به آن متصل شود.</footer>
    </main>
  );
}
