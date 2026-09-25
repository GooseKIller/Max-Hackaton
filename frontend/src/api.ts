export type Category =
  "spektakli" | "vystavki" | "koncerty" | "ekskursii" | "kino" | "prochie";
export type Availability = "both" | "evenings" | "weekends";
export interface Meta {
  city: string;
  synthetic: boolean;
  catalogue_as_of: string;
  horizon_end: string;
  total_limit: number;
  cinema_limit: number;
  age_min: number;
  age_max: number;
  rules_as_of: string;
  rules_source: string;
  categories: { id: Category; label: string }[];
}
export interface Event {
  id: number;
  title: string;
  category: string;
  category_label: string;
  description: string;
  venue: string;
  address: string;
  age: number;
  start: string;
  end: string;
  price: number;
  price_is_minimum: boolean;
  ticket_url: string | null;
}
export interface Plan {
  kind: "interests" | "variety" | "budget";
  title: string;
  explanation: string;
  events: Event[];
  total: number;
  cinema_total: number;
  remaining: number;
  estimated: boolean;
}
export interface Result {
  status: "ready" | "no_plans" | "no_events" | "horizon_ended";
  plans: Plan[];
  events: Event[];
  balance: number;
  cinema_balance: number | null;
  calculated_at: string;
  synthetic: boolean;
  catalogue_as_of: string;
  horizon_end: string;
  transfer_minutes: number;
}
export interface PlanInput {
  age: number;
  balance: number;
  cinema_balance: number | null;
  categories: Category[];
  availability: Availability;
}

export async function request<T>(path: string, body?: PlanInput): Promise<T> {
  const response = await fetch(`/api/planner/${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok)
    throw new Error(
      response.status === 422
        ? "Проверь возраст и суммы: остаток на кино не должен превышать общий."
        : "Сервис подбора не ответил. Попробуй ещё раз — введённые данные остались в форме.",
    );
  return response.json();
}

export const money = (value: number) => `${value.toLocaleString("ru-RU")} ₽`;
// Seances are Kazan wall-clock times, not dates to convert to the viewer's timezone.
export const when = (iso: string) => {
  const [day, time] = iso.split("T");
  const label = new Date(`${day}T12:00:00Z`).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    weekday: "short",
    timeZone: "UTC",
  });
  return `${label} · ${time.slice(0, 5)}`;
};
export const price = (event: Event) =>
  `${event.price_is_minimum ? "от " : ""}${money(event.price)}`;

declare global {
  interface Window {
    WebApp?: {
      initData?: string;
      openLink?: (url: string) => void;
      BackButton?: {
        show(): void;
        hide(): void;
        onClick(fn: () => void): void;
        offClick(fn: () => void): void;
      };
    };
  }
}
