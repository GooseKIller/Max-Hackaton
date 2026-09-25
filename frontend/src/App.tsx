import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  money,
  price,
  request,
  when,
  type Availability,
  type Category,
  type Event,
  type Meta,
  type Plan,
  type Result,
} from "./api";
import { PreferenceSheet, TIME_LABELS } from "./PreferenceSheet";
import { Icon } from "./Icon";

const COPY = {
  privacy:
    "Без номера карты и даты рождения. Данные этой формы используются для расчёта и не сохраняются в профиль бота.",
  demo: "Демо-каталог: события сгенерированы, купить билеты на них нельзя.",
  estimate:
    "Считаем по ценам каталога. Реальная цена выбранных мест может быть выше бюджета — проверь её у продавца.",
  noPlans: "На целый план не набралось",
  noEvents: "Под эти условия событий не нашлось",
};

function TicketLink({ event }: { event: Event }) {
  if (!event.ticket_url)
    return <span className="unavailable">Ссылка на билет недоступна</span>;
  return (
    <a
      className="ticket-link"
      href={event.ticket_url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => {
        if (window.WebApp?.initData && window.WebApp.openLink) {
          try {
            window.WebApp.openLink(event.ticket_url!);
            e.preventDefault();
          } catch {
            /* Keep ordinary link fallback. */
          }
        }
      }}
    >
      Проверить билеты <span aria-hidden="true">↗</span>
    </a>
  );
}

function EventCard({ event, synthetic }: { event: Event; synthetic: boolean }) {
  return (
    <article className="event-card">
      <div
        className={`event-icon category-${event.category}`}
        aria-hidden="true"
      >
        {event.category === "kino"
          ? "▶"
          : event.category === "koncerty"
            ? "♫"
            : "✳"}
      </div>
      <div className="event-body">
        <div className="eyebrow">
          {event.category_label} · {event.age}+
        </div>
        <h3>{event.title}</h3>
        <p>{when(event.start)}</p>
        <p className="muted">{event.venue}</p>
        <div className="event-bottom">
          <strong>{price(event)}</strong>
          {!synthetic && <TicketLink event={event} />}
        </div>
      </div>
    </article>
  );
}

function PlanCard({
  plan,
  index,
  onOpen,
}: {
  plan: Plan;
  index: number;
  onOpen: () => void;
}) {
  return (
    <article className={`plan-card plan-${plan.kind}`}>
      <div className="plan-top">
        <span className="eyebrow">Вариант {index + 1}</span>
        <span className="count">{plan.events.length} события</span>
      </div>
      <h3>{plan.title}</h3>
      <ol className="plan-events">
        {plan.events.map((event) => (
          <li key={event.id}>
            <span className="timeline-dot" />
            <div>
              <span className="event-type">{event.category_label}</span>
              <h4>{event.title}</h4>
              <p>{when(event.start)}</p>
            </div>
            <span className="event-price">{price(event)}</span>
          </li>
        ))}
      </ol>
      <div className="plan-total">
        <div>
          <span>{plan.estimated ? "Сумма от" : "Сумма"}</span>
          <strong>{money(plan.total)}</strong>
        </div>
        <div>
          <span>{plan.estimated ? "Остаток до" : "Остаток"}</span>
          <strong>{money(plan.remaining)}</strong>
        </div>
      </div>
      <button className="plan-open" onClick={onOpen}>
        Посмотреть план <span aria-hidden="true">›</span>
      </button>
    </article>
  );
}

function PlanDetails({
  plan,
  result,
  close,
}: {
  plan: Plan;
  result: Result;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    dialog.showModal();
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const back = window.WebApp?.initData ? window.WebApp.BackButton : undefined;
    back?.show();
    back?.onClick(close);
    return () => {
      dialog.close();
      document.body.style.overflow = oldOverflow;
      back?.offClick(close);
      back?.hide();
      opener?.focus();
    };
  }, [close]);
  return (
    <dialog
      ref={ref}
      aria-labelledby="detail-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="detail-content">
        <header className="detail-heading">
          <div>
            <h2 id="detail-title">{plan.title}</h2>
          </div>
          <button className="close" aria-label="Закрыть план" onClick={close}>
            ×
          </button>
        </header>
        <p>{plan.explanation}</p>
        <div className="detail-budget">
          <span>Ты указал {money(result.balance)}</span>
          <strong>
            {plan.estimated ? "Сумма от " : "Сумма "}
            {money(plan.total)}
          </strong>
          <span>
            {plan.estimated ? "Расчётный остаток до " : "Расчётный остаток "}
            {money(plan.remaining)}
          </span>
          {plan.cinema_total > 0 && (
            <span>Из суммы на кино: {money(plan.cinema_total)}</span>
          )}
        </div>
        {result.synthetic && <p className="notice">{COPY.demo}</p>}
        <ol className="detail-events">
          {plan.events.map((event, index) => (
            <li key={event.id}>
              <span className="detail-number">0{index + 1}</span>
              <div>
                <p className="eyebrow">
                  {event.category_label} · {event.age}+
                </p>
                <h3>{event.title}</h3>
                <p>
                  <strong>{when(event.start)}</strong> — до{" "}
                  {event.end.slice(11, 16)}
                </p>
                <p>
                  {event.venue}
                  {event.address && ` · ${event.address}`}
                </p>
                <p className="muted">{event.description}</p>
                <div className="event-bottom">
                  <strong>{price(event)}</strong>
                  {!result.synthetic && <TicketLink event={event} />}
                </div>
              </div>
            </li>
          ))}
        </ol>
        <div className="detail-notes">
          <p>{COPY.estimate}</p>
          <p>
            Между событиями заложено {result.transfer_minutes} минут. Это запас,
            а не расчёт маршрута: время дороги проверь отдельно. Время событий —
            казанское.
          </p>
          <p>
            Это план, не бронь. Каждый билет покупается отдельно. Деньги с карты
            не списаны.
          </p>
        </div>
        <button className="primary full" onClick={close}>
          Вернуться к вариантам
        </button>
      </div>
    </dialog>
  );
}

export function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [balance, setBalance] = useState("");
  const [age, setAge] = useState("");
  const [cinema, setCinema] = useState("");
  const [includeCinema, setIncludeCinema] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [availability, setAvailability] = useState<Availability>("both");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Plan | null>(null);
  const [preference, setPreference] = useState<"interests" | "time" | null>(
    null,
  );
  const closePreference = useCallback(() => setPreference(null), []);
  const resultsRef = useRef<HTMLElement>(null);
  const close = useCallback(() => setSelected(null), []);
  const loadMeta = useCallback(() => {
    setMetaError(false);
    request<Meta>("meta")
      .then(setMeta)
      .catch(() => setMetaError(true));
  }, []);
  useEffect(loadMeta, [loadMeta]);
  // Editing removes the old calculation so its amounts cannot masquerade as current.
  const invalidate = () => {
    setResult(null);
    setSelected(null);
    setError("");
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!meta || loading) return;
    if (
      !/^\d+$/.test(balance) ||
      !age ||
      (includeCinema && !/^\d+$/.test(cinema))
    ) {
      setError(
        "Укажи возраст и точный остаток в целых рублях. Для подбора без кино его остаток не нужен.",
      );
      return;
    }
    if (
      +balance > meta.total_limit ||
      (includeCinema && (+cinema > +balance || +cinema > meta.cinema_limit))
    ) {
      setError(
        "Проверь суммы: остаток на кино входит в общий остаток, а не прибавляется к нему.",
      );
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await request<Result>("plans", {
        age: +age,
        balance: +balance,
        cinema_balance: includeCinema ? +cinema : null,
        categories,
        availability,
      });
      setResult(data);
      requestAnimationFrame(() =>
        resultsRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        }),
      );
    } catch (err) {
      setError(
        err instanceof Error &&
          !["TimeoutError", "TypeError"].includes(err.name)
          ? err.message
          : "Не удалось загрузить планы. Проверь соединение и попробуй ещё раз — форма не сбросилась.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <a className="skip-link" href="#parameters">
        К подбору плана
      </a>
      <div className="page">
        <header className="site-header" id="top">
          <div className="app-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <rect
                x="4"
                y="3"
                width="16"
                height="18"
                rx="3"
                stroke="currentColor"
                strokeWidth="1.8"
              />
              <path
                d="m8 12 3 3 5-6M8 6h8"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <h1>Планы по Пушкинской карте</h1>
          </div>
        </header>
        <main>
          {meta?.synthetic && (
            <aside className="demo-banner">
              <strong>Демо</strong>
              <span>{COPY.demo}</span>
            </aside>
          )}
          <section
            className="workspace"
            id="parameters"
            aria-labelledby="form-title"
          >
            <div className="section-intro">
              <h2 id="form-title">Подобрать события</h2>
            </div>
            <form
              onSubmit={submit}
              className="planner-form"
              aria-busy={loading}
            >
              {!meta && (
                <div role="status" className="notice">
                  {metaError ? (
                    <>
                      Не удалось загрузить условия подбора.{" "}
                      <button
                        type="button"
                        className="text-button"
                        onClick={loadMeta}
                      >
                        Повторить
                      </button>
                    </>
                  ) : (
                    "Загружаем условия подбора…"
                  )}
                </div>
              )}
              <fieldset disabled={loading || !meta} className="form-fields">
                <legend className="sr-only">Условия подбора</legend>
                <div className="budget-row">
                  <div className="balance-label">
                    <label htmlFor="balance">Остаток на карте</label>
                    <div className="money-input">
                      <input
                        id="balance"
                        name="balance"
                        value={balance}
                        placeholder="Сумма"
                        inputMode="numeric"
                        pattern="[0-9]+"
                        maxLength={4}
                        required
                        aria-describedby="balance-help"
                        onChange={(e) => {
                          invalidate();
                          setBalance(e.target.value);
                        }}
                      />
                      <span aria-hidden="true">₽</span>
                    </div>
                  </div>
                  <div>
                    <label htmlFor="age">Возраст</label>
                    <select
                      id="age"
                      required
                      value={age}
                      onChange={(e) => {
                        invalidate();
                        setAge(e.target.value);
                      }}
                    >
                      <option value="" disabled>
                        Выбери
                      </option>
                      {meta &&
                        Array.from(
                          { length: meta.age_max - meta.age_min + 1 },
                          (_, i) => i + meta.age_min,
                        ).map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                    </select>
                  </div>
                </div>
                <p className="field-hint" id="balance-help">
                  Введи точную сумму из «Госуслуги Культура». Мы не видим баланс
                  карты.
                </p>
                <div className="cinema-box">
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={includeCinema}
                      onChange={(e) => {
                        invalidate();
                        setIncludeCinema(e.target.checked);
                        if (!e.target.checked)
                          setCategories((c) => c.filter((v) => v !== "kino"));
                      }}
                    />
                    Учитывать кино
                  </label>
                  {includeCinema ? (
                    <div className="cinema-entry">
                      <label htmlFor="cinema">
                        Сколько ещё доступно на кино?
                        <input
                          id="cinema"
                          value={cinema}
                          inputMode="numeric"
                          pattern="[0-9]+"
                          maxLength={4}
                          placeholder="Точная сумма, ₽"
                          required
                          onChange={(e) => {
                            invalidate();
                            setCinema(e.target.value);
                          }}
                        />
                      </label>
                      <p className="field-hint">
                        Не больше {money(meta?.cinema_limit ?? 0)} и общего
                        остатка. Не знаешь — выключи кино.
                      </p>
                    </div>
                  ) : (
                    <p className="field-hint">
                      Пока подбираем без кино: у него отдельное ограничение
                      внутри общего остатка.
                    </p>
                  )}
                </div>
                <p className="group-caption">Предпочтения</p>
                <div className="settings-group">
                  <button
                    type="button"
                    className="setting-row"
                    aria-haspopup="dialog"
                    onClick={() => setPreference("interests")}
                  >
                    <span className="row-icon purple" aria-hidden="true">
                      <Icon name="heart" />
                    </span>
                    <span>Интересы</span>
                    <span className="row-value">
                      {categories.length
                        ? meta?.categories
                            .filter((c) => categories.includes(c.id))
                            .map((c) => c.label)
                            .join(", ")
                        : "Все форматы"}
                    </span>
                    <span className="chevron" aria-hidden="true">
                      ›
                    </span>
                  </button>
                  <button
                    type="button"
                    className="setting-row"
                    aria-haspopup="dialog"
                    onClick={() => setPreference("time")}
                  >
                    <span className="row-icon blue" aria-hidden="true">
                      <Icon name="clock" />
                    </span>
                    <span>Когда</span>
                    <span className="row-value">
                      {TIME_LABELS[availability]}
                    </span>
                    <span className="chevron" aria-hidden="true">
                      ›
                    </span>
                  </button>
                </div>
                <p className="field-hint">
                  Будни — с 16:00, выходные — с 09:00. Время Казани.
                </p>
                <button className="primary submit" type="submit">
                  {loading ? "Собираем планы…" : "Собрать мой план"}
                  <span aria-hidden="true">{loading ? "◌" : "→"}</span>
                </button>
              </fieldset>
              {error && (
                <p role="alert" className="error">
                  {error}
                </p>
              )}
              <p className="form-footnote">
                Подбор ничего не списывает и не бронирует.
              </p>
              <details className="privacy-note">
                <summary>Что будет с моими данными?</summary>
                <p>{COPY.privacy}</p>
              </details>
            </form>
          </section>
          <section
            ref={resultsRef}
            id="results"
            className="results"
            aria-labelledby="result-title"
            aria-busy={loading}
            hidden={!loading && !result}
          >
            <div className="results-heading">
              <h2 id="result-title">
                {result?.plans.length ? "Варианты планов" : "Твой план"}
              </h2>
              {result && (
                <a className="text-button" href="#parameters">
                  Изменить условия
                </a>
              )}
            </div>
            <div role="status" aria-live="polite" className="sr-only">
              {loading
                ? "Идёт подбор планов"
                : result
                  ? `Подбор завершён. Планов: ${result.plans.length}. Отдельных событий: ${result.events.length}.`
                  : "Укажи условия для подбора."}
            </div>
            {loading ? (
              <div className="loading-state">
                <span className="spinner" />
                <p>Проверяем суммы и время событий…</p>
              </div>
            ) : !result ? (
              <div className="initial-state">
                <p>
                  Укажи остаток и нажми «Собрать мой план».
                  <br />
                  Здесь появятся подходящие варианты.
                </p>
              </div>
            ) : (
              <>
                <div className="result-context">
                  <span>
                    Ты указал <strong>{money(result.balance)}</strong>
                  </span>
                  <span>Расчёт: {when(result.calculated_at)}</span>
                  {result.cinema_balance === null && <span>Без кино</span>}
                </div>
                {result.synthetic && !meta?.synthetic && (
                  <p className="notice">{COPY.demo}</p>
                )}
                {result.plans.length ? (
                  <>
                    <div className="plans-grid">
                      {result.plans.map((plan, index) => (
                        <PlanCard
                          key={plan.kind}
                          plan={plan}
                          index={index}
                          onOpen={() => setSelected(plan)}
                        />
                      ))}
                    </div>
                    <p className="result-caveat">
                      {COPY.estimate} Планы — альтернативы: их суммы не нужно
                      складывать.
                    </p>
                  </>
                ) : (
                  <div className="empty-state">
                    <span aria-hidden="true">↳</span>
                    <div>
                      <h3>
                        {result.status === "horizon_ended"
                          ? "Период подбора закончился"
                          : result.status === "no_plans"
                            ? COPY.noPlans
                            : COPY.noEvents}
                      </h3>
                      <p>
                        {result.status === "horizon_ended"
                          ? "Каталог и правила рассчитаны до конца 2026 года. Для нового периода их нужно обновить."
                          : result.status === "no_plans"
                            ? "Можно выбрать отдельное событие ниже. Или изменить время и форматы — остаток увеличивать не обязательно."
                            : "Попробуй другие форматы или время. Если выбор не появится, в нашем небольшом каталоге пока нет подходящих вариантов."}
                      </p>
                      <a className="text-button" href="#parameters">
                        Вернуться к условиям ↑
                      </a>
                    </div>
                  </div>
                )}
                {result.events.length > 0 && (
                  <section className="singles">
                    <div className="results-heading">
                      <h2>Можно и по одному</h2>
                    </div>
                    <p className="muted">
                      Каждое событие подходит по условиям. Сумма нескольких
                      может превысить остаток.
                    </p>
                    <div className="events-grid">
                      {result.events.map((event) => (
                        <EventCard
                          key={event.id}
                          event={event}
                          synthetic={result.synthetic}
                        />
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </section>
        </main>
        <footer>
          <p>Не официальный сервис программы</p>
          {meta && (
            <a
              href={meta.rules_source}
              target="_blank"
              rel="noopener noreferrer"
            >
              Правила программы ↗<small>Проверены {meta.rules_as_of}</small>
            </a>
          )}
        </footer>
      </div>
      {selected && result && (
        <PlanDetails plan={selected} result={result} close={close} />
      )}
      {preference && meta && (
        <PreferenceSheet
          kind={preference}
          meta={meta}
          categories={categories}
          availability={availability}
          includeCinema={includeCinema}
          close={closePreference}
          onApply={(nextCategories, nextAvailability) => {
            invalidate();
            setCategories(nextCategories);
            setAvailability(nextAvailability);
            setPreference(null);
          }}
        />
      )}
    </>
  );
}
