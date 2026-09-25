import { test, expect, type Page } from "@playwright/test";

const meta = {
  city: "Казань",
  synthetic: true,
  catalogue_as_of: "2026-09-25",
  horizon_end: "2026-12-31",
  total_limit: 5000,
  cinema_limit: 2000,
  age_min: 14,
  age_max: 22,
  rules_as_of: "2026-09-25",
  rules_source: "https://www.culture.ru/pushkinskaya-karta",
  categories: [
    { id: "spektakli", label: "Театр" },
    { id: "vystavki", label: "Выставки" },
    { id: "kino", label: "Кино" },
  ],
};
const events = [
  {
    id: 1,
    title: "Спектакль о выборе",
    category: "spektakli",
    category_label: "Театр",
    description: "Тестовое описание, а не настоящая афиша.",
    venue: "Тестовый театр",
    address: "Тестовый адрес",
    age: 12,
    start: "2026-10-03T18:00:00",
    end: "2026-10-03T19:30:00",
    price: 1200,
    price_is_minimum: true,
    ticket_url: null,
  },
  {
    id: 2,
    title: "Выставка нового искусства",
    category: "vystavki",
    category_label: "Выставки",
    description: "Тестовое описание.",
    venue: "Тестовый музей",
    address: "",
    age: 6,
    start: "2026-10-04T14:00:00",
    end: "2026-10-04T15:00:00",
    price: 600,
    price_is_minimum: false,
    ticket_url: null,
  },
];
const result = {
  status: "ready",
  plans: [
    {
      kind: "interests",
      title: "Под твои условия",
      explanation: "Выше в подборе по выбранным условиям.",
      events,
      total: 1800,
      remaining: 1200,
      cinema_total: 0,
      estimated: true,
    },
  ],
  events,
  balance: 3000,
  cinema_balance: null,
  calculated_at: "2026-09-25T12:00:00",
  synthetic: true,
  catalogue_as_of: "2026-09-25",
  horizon_end: "2026-12-31",
  transfer_minutes: 45,
};

test.beforeEach(async ({ page }) => {
  // Tests do not need a remote SDK or any MAX account.
  await page.route("https://st.max.ru/**", (route) =>
    route.fulfill({ body: "" }),
  );
  await page.route("**/api/planner/meta", (route) =>
    route.fulfill({ json: meta }),
  );
  await page.route("**/api/planner/plans", (route) =>
    route.fulfill({ json: result }),
  );
});

async function fill(page: Page) {
  await page.goto("/app/");
  await page.getByLabel("Остаток на карте", { exact: true }).fill("3000");
  await page.getByLabel("Возраст", { exact: true }).selectOption("18");
}

test("initial screen has no invented balance, no horizontal overflow", async ({
  page,
}, info) => {
  await page.goto("/app/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Планы по Пушкинской карте",
  );
  await expect(
    page.getByLabel("Остаток на карте", { exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByText("Демо-каталог:", { exact: false }).first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("initial.png"),
    fullPage: true,
  });
});

test("calculation, details, escape and stale-result invalidation", async ({
  page,
}, info) => {
  await fill(page);
  const sent = page.waitForRequest("**/api/planner/plans");
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  expect((await sent).postDataJSON()).toEqual({
    age: 18,
    balance: 3000,
    cinema_balance: null,
    categories: [],
    availability: "both",
  });
  await expect(
    page.getByRole("button", { name: "Посмотреть план" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("results.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Посмотреть план" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("Сумма от", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Проверить билеты" }),
  ).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("details.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Посмотреть план" }),
  ).toBeFocused();
  await page.getByLabel("Остаток на карте", { exact: true }).fill("1500");
  await expect(
    page.getByRole("button", { name: "Посмотреть план" }),
  ).toHaveCount(0);
});

test("cinema is explicit and cannot add a second wallet", async ({ page }) => {
  await fill(page);
  await page.getByLabel("Учитывать кино", { exact: true }).check();
  await page.getByLabel("Сколько ещё доступно на кино?").fill("2000");
  await page.getByRole("button", { name: /^Интересы/ }).click();
  await page.getByRole("checkbox", { name: "Кино", exact: true }).check();
  await page.getByRole("button", { name: "Готово", exact: true }).click();
  await page.getByLabel("Остаток на карте", { exact: true }).fill("1000");
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "остаток на кино входит в общий",
  );
  await page.getByLabel("Учитывать кино", { exact: true }).uncheck();
  await expect(
    page.getByRole("button", { name: "Кино", exact: true }),
  ).toHaveCount(0);
  const sent = page.waitForRequest("**/api/planner/plans");
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  expect((await sent).postDataJSON().cinema_balance).toBeNull();
  expect((await sent).postDataJSON().categories).toEqual([]);
});

test("preference sheets apply choices and discard cancelled edits", async ({
  page,
}) => {
  await fill(page);
  await page.getByRole("button", { name: /^Интересы/ }).click();
  await page.getByRole("checkbox", { name: "Театр", exact: true }).check();
  await page.getByRole("button", { name: "Закрыть настройки" }).click();
  await expect(page.getByRole("button", { name: /^Интересы/ })).toContainText(
    "Все форматы",
  );
  await page.getByRole("button", { name: /^Интересы/ }).click();
  await page.getByRole("checkbox", { name: "Театр", exact: true }).check();
  await page.getByRole("button", { name: "Готово", exact: true }).click();
  await expect(page.getByRole("button", { name: /^Интересы/ })).toContainText(
    "Театр",
  );
  await page.getByRole("button", { name: /^Когда/ }).click();
  await page.getByRole("radio", { name: /^В выходные/ }).check();
  await page.getByRole("button", { name: "Готово", exact: true }).click();
  const sent = page.waitForRequest("**/api/planner/plans");
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  expect((await sent).postDataJSON()).toMatchObject({
    categories: ["spektakli"],
    availability: "weekends",
  });
});

test("loading prevents duplicate calculations", async ({ page }) => {
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/planner/plans", async (route) => {
    await gate;
    await route.fulfill({ json: result });
  });
  await fill(page);
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(
    page.getByRole("button", { name: "Собираем планы" }),
  ).toBeDisabled();
  await expect(
    page.getByLabel("Остаток на карте", { exact: true }),
  ).toBeDisabled();
  release();
  await expect(
    page.getByRole("button", { name: "Посмотреть план" }),
  ).toBeVisible();
});

test("network error preserves inputs and supports retry", async ({ page }) => {
  await page.route("**/api/planner/plans", (route) => route.abort());
  await fill(page);
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(page.getByRole("alert")).toContainText("Проверь соединение");
  await expect(
    page.getByLabel("Остаток на карте", { exact: true }),
  ).toHaveValue("3000");
  await page.route("**/api/planner/plans", (route) =>
    route.fulfill({ json: result }),
  );
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(
    page.getByRole("button", { name: "Посмотреть план" }),
  ).toBeVisible();
});

test("single-event fallback, no-events and expired horizon have exits", async ({
  page,
}) => {
  await page.route("**/api/planner/plans", (route) =>
    route.fulfill({ json: { ...result, status: "no_plans", plans: [] } }),
  );
  await fill(page);
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(page.getByText("На целый план не набралось")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Можно и по одному" }),
  ).toBeVisible();
  await page.route("**/api/planner/plans", (route) =>
    route.fulfill({
      json: { ...result, status: "no_events", plans: [], events: [] },
    }),
  );
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(
    page.getByText("Под эти условия событий не нашлось"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Вернуться к условиям" }),
  ).toBeVisible();
  await page.route("**/api/planner/plans", (route) =>
    route.fulfill({
      json: { ...result, status: "horizon_ended", plans: [], events: [] },
    }),
  );
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(page.getByText("Период подбора закончился")).toBeVisible();
});

test("metadata failure can be retried", async ({ page }) => {
  await page.route("**/api/planner/meta", (route) => route.abort());
  await page.goto("/app/");
  await expect(
    page.getByRole("button", { name: "Собрать мой план" }),
  ).toBeDisabled();
  await page.route("**/api/planner/meta", (route) =>
    route.fulfill({ json: meta }),
  );
  await page.getByRole("button", { name: "Повторить" }).click();
  await expect(
    page.getByRole("button", { name: "Собрать мой план" }),
  ).toBeEnabled();
});

test("real API integration, not an intercepted calculation", async ({
  page,
}) => {
  await page.unroute("**/api/planner/meta");
  await page.unroute("**/api/planner/plans");
  await fill(page);
  const response = page.waitForResponse("**/api/planner/plans");
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  const data = await (await response).json();
  expect(data.balance).toBe(3000);
  expect(data.status).toMatch(/^(ready|no_plans|no_events|horizon_ended)$/);
  for (const plan of data.plans) expect(plan.total + plan.remaining).toBe(3000);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.locator(".result-context")).toContainText("3 000");
});

test("dark mode and long titles remain readable at narrow widths", async ({
  page,
}, info) => {
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.setViewportSize({ width: 320, height: 720 });
  const longEvents = events.map((e) => ({
    ...e,
    title: "Очень длинное название спектакля об истории и современности Казани",
  }));
  await page.route("**/api/planner/plans", (route) =>
    route.fulfill({
      json: {
        ...result,
        plans: result.plans.map((p) => ({ ...p, events: longEvents })),
        events: longEvents,
      },
    }),
  );
  await fill(page);
  await page.getByRole("button", { name: "Собрать мой план" }).click();
  await expect(
    page.getByRole("button", { name: "Посмотреть план" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("dark-narrow.png"),
    fullPage: true,
  });
});
