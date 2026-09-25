import { useEffect, useRef, useState } from "react";
import type { Availability, Category, Meta } from "./api";

export const TIME_LABELS: Record<Availability, string> = {
  both: "Вечером и в выходные",
  weekends: "В выходные",
  evenings: "В будни вечером",
};

export function PreferenceSheet({
  kind,
  meta,
  categories,
  availability,
  includeCinema,
  onApply,
  close,
}: {
  kind: "interests" | "time";
  meta: Meta;
  categories: Category[];
  availability: Availability;
  includeCinema: boolean;
  onApply: (categories: Category[], availability: Availability) => void;
  close: () => void;
}) {
  const [draftCategories, setDraftCategories] = useState(categories);
  const [draftTime, setDraftTime] = useState(availability);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    dialog.showModal();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const back = window.WebApp?.initData ? window.WebApp.BackButton : undefined;
    back?.show();
    back?.onClick(close);
    return () => {
      dialog.close();
      document.body.style.overflow = previous;
      back?.offClick(close);
      back?.hide();
      opener?.focus();
    };
  }, [close]);
  const toggle = (category: Category) =>
    setDraftCategories((current) =>
      current.includes(category)
        ? current.filter((c) => c !== category)
        : [...current, category],
    );

  return (
    <dialog
      ref={ref}
      className="preference-sheet"
      aria-labelledby="preference-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="sheet-handle" aria-hidden="true" />
      <header className="sheet-header">
        <h2 id="preference-title">
          {kind === "interests" ? "Что интересно?" : "Когда удобно?"}
        </h2>
        <button
          type="button"
          className="close"
          aria-label="Закрыть настройки"
          onClick={close}
        >
          ×
        </button>
      </header>
      <p className="sheet-hint">
        {kind === "interests"
          ? "Выбери несколько форматов или оставь все."
          : "Время событий — казанское."}
      </p>
      <div className="sheet-options">
        {kind === "interests" ? (
          <>
            <label className="sheet-option">
              <span>Все форматы</span>
              <input
                type="checkbox"
                checked={draftCategories.length === 0}
                onChange={() => setDraftCategories([])}
              />
            </label>
            {meta.categories
              .filter((c) => c.id !== "kino" || includeCinema)
              .map((c) => (
                <label className="sheet-option" key={c.id}>
                  <span>{c.label}</span>
                  <input
                    type="checkbox"
                    checked={draftCategories.includes(c.id)}
                    onChange={() => toggle(c.id)}
                  />
                </label>
              ))}
          </>
        ) : (
          (Object.entries(TIME_LABELS) as [Availability, string][]).map(
            ([value, label]) => (
              <label className="sheet-option" key={value}>
                <span>
                  {label}
                  <small>
                    {value === "both"
                      ? "Будни с 16:00, выходные с 09:00"
                      : value === "weekends"
                        ? "Суббота и воскресенье, с 09:00"
                        : "Понедельник — пятница, с 16:00"}
                  </small>
                </span>
                <input
                  type="radio"
                  name="sheet-time"
                  checked={draftTime === value}
                  onChange={() => setDraftTime(value)}
                />
              </label>
            ),
          )
        )}
      </div>
      <div className="sheet-action">
        <button
          className="primary full"
          type="button"
          onClick={() => onApply(draftCategories, draftTime)}
        >
          Готово
        </button>
      </div>
    </dialog>
  );
}
