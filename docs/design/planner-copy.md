# Planner: screen copy and demo script

Implemented in this branch, 25 September 2026. Source of executable copy:
`frontend/src/App.tsx`; bot equivalents: `backend/app/dialog.py`.

## What the product says

> Подбери 2–3 события по Пушкинской карте под свой остаток, интересы и свободное
> время. Сразу увидишь общую сумму и расчётный остаток. Можно выбрать и одно событие.

No “spend everything at any cost”, artificial urgency, claimed exclusive capability,
hidden balance access or predicted purchases. The interface follows familiar messenger
patterns at the user's request; this is a design preference, not a researched uplift.
Specifically: inset groups of label/value rows rather than filled web-form boxes,
separate bottom sheets for interests/time, draft choices applied only by “Готово”.
Visual palette is a custom blue/violet/pale-pink interpretation of MAX + Pushkin Card,
not Telegram branding or official co-brand approval. No decorative gradients or hero.

## Screen / state inventory

| Trigger | User-facing text / action | Constraint |
|---|---|---|
| First visit | «Подобрать события» | No decorative subtitles (“Казань · Пилот”), repeated explanations or made-up balance prefilled |
| Budget input | «Введи точную сумму из „Госуслуги Культура“. Мы не видим баланс карты» | Exact rubles, not a range |
| Cinema off | «Пока подбираем без кино: у него отдельное ограничение внутри общего остатка» | No guessed 2,000 available |
| Cinema on | «Сколько ещё доступно на кино?» | Not above total/annual cinema limit |
| Interest selection | «Что интересно? Можно несколько» | Empty selection = all formats |
| Time selection | «Будни — с 16:00, выходные — с 09:00. Время Казани» | Fixed MVP time windows, not an availability calendar |
| Submit | «Собрать мой план» | Does not debit, book or save a purchase |
| Loading | «Проверяем суммы и время событий…» | No fake progress percentages |
| Results | «Под твои условия» / «Разные форматы» / «Ближе к остатку» | Up to three distinct sets, fewer is fine |
| Variable price | «Сумма от …» / «Остаток до …» | Seller's final price can exceed budget |
| Plan details | «Это план, не бронь. Каждый билет покупается отдельно. Деньги с карты не списаны» | Opening is not selecting or buying |
| Link out | «Проверить билеты» | Only real non-synthetic HTTPS URLs; no invented URLs |
| No plan, some events | «На целый план не набралось» / separate events below | Do not tell the user to lower the balance to create choices |
| No events | «Под эти условия событий не нашлось» / «Вернуться к условиям» | No claims that the whole city lacks events |
| Network failure | «…форма не сбросилась» | Retry through the same submit button |
| Synthetic data | «Демо-каталог: события сгенерированы, купить билеты на них нельзя» | Visible before entering data and in details |
| Expired horizon | «Период подбора закончился» | Do not silently move old dates into the future |

## 60-second demo for teammates / presentation

1. Open `/app/`. Point to the demo notice: this demonstrates the mechanics, not real stock.
2. Enter test age **18** and **3,000 ₽**. Leave cinema off because its remaining
   allowance is unknown. Choose time/formats, or keep all formats.
3. Submit. Explain that Python filters eligible candidates and checks 2–3-event
   combinations, including aggregate budgets and non-overlapping times.
4. Open one plan. Show the venue, Kazan date/time, sum and remainder. If prices vary,
   point out “от/до”; a final seller check is still necessary.
5. Return to the form and enter **1,500 ₽**. Old plans disappear until recalculation:
   this prevents a new balance from being displayed beside an old cost.
6. Show the single-event fallback if available. The user does not have to exhaust
   the balance to get value.

The example requires the fixture to contain future dates within the configured year.
If it has aged, demonstrate the honest empty state or use the fixed test fixtures in
the automated suite; do not pass backdated output off as current availability.

## Task for the first five testers

«Представь, что на карте осталось 3 000 ₽, а остаток на кино ты не помнишь.
Найди вариант, на который ты действительно согласился бы пойти в выходные.
Скажи, сколько он стоит и что нужно проверить перед покупкой».

Watch without explaining the UI. Record time, mistakes, which plan/event was acceptable,
whether they understand “от/до”, separate tickets and unknown cinema. Ask: «Что здесь
было лишним? Чего не хватило для решения?» Do not count opening a details sheet as a
purchase or a firm choice. Field tests remain pending.

## Team handoff message

> В нашей ветке готов блок «планы под бюджет»: Python API и React-интерфейс с
> остатком, интересами, временем, карточками планов и подробностями событий.
> Визуально — спокойное мини-приложение с привычными списками и переключателями.
> Код учитывает общий остаток и ограничение на кино, показывает примерные цены и
> умеет объяснять пустую выдачу. Тексты состояний и сценарий демонстрации собраны.
> Пока это самостоятельный расчёт без синхронизации с профилем бота; каталог
> тестовый. До живого демо нужны реальные события, HTTPS и проверка внутри MAX.
