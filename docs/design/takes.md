# Product takes: reviewed positioning and Russian copy

Status: proposed for team review, 25 September 2026. Adapted from the local draft
`takes.md`. This document distinguishes implemented behaviour, design choices and
hypotheses. Evidence and its limits: [validation.md](../research/validation.md).

## Positioning

> Помогаем выбрать, куда хочется пойти по Пушкинской карте: учитываем интересы,
> выбранное время и указанный остаток, предлагаем события или готовый план
> и объясняем подбор.

This is a proposed value proposition, not evidence of increased spending. The current
branch implements a bot with ranking and plans on a synthetic catalogue. A mini app,
scheduled reminders and cultural-anchor matching remain separate work packages.

## Messages we can defend

| Take | Why we can say it | Boundary |
|---|---|---|
| «События под твой остаток и выбранное время» | Hard filters use the user's input | Self-reported balance; catalogue prices may be lower bounds |
| «Несколько событий — в одном плане» | `build_plans` checks 2–3-event combinations | A suggestion, not a basket, reservation or payment |
| «Отметь интересное — следующие варианты изменятся» | Quiz signals update a taste vector | Not an individual prediction of attendance or a trained TikTok algorithm |
| «Показываем, почему это подходит» | Explain a real score/filter used | No invented shared worlds, travel times or preferences |
| «Можно выбрать по интересам, разнообразию или сумме» | Planner offers distinct alternatives where feasible | Fewer alternatives are acceptable; no global optimum claim |

The proposed priority audience is a Kazan cardholder aged 15–18 who wants to choose
an outing independently. This is a pilot recruitment decision, not a deduction that
all or most Russian cardholders are school students. Include 19–22-year-olds in
exploratory interviews to test whether the chosen segment is actually the best fit.

## Tone decisions

Use plain Russian, a useful explanation and specific event details. Avoid forced
slang, blame and manufactured urgency. These are design choices to test, not universal
psychological laws. A real deadline may be shown calmly; a countdown is not prohibited
merely because it is a countdown. Do not describe unspent funds as the user's failure.

Transparency makes a recommendation easier to inspect. It does not guarantee trust
or make a persuasive message incapable of manipulation.

## Russian copy

Implemented flow (the exact executable strings live in `backend/app/dialog.py`):

- Start: «Помогу выбрать, на что потратить Пушкинскую карту в Казани.
  Несколько вопросов, потом покажу варианты. Сколько тебе лет?»
- Total balance: «Сколько осталось на карте? Введи точную сумму или выбери
  „не знаю“, чтобы посмотреть события без расчёта плана.»
- Cinema: «Сколько из остатка ещё можно потратить на кино? Если не знаешь,
  подберу события без кино.»
- Unknown balance: «Остаток пока не указан; доступность по бюджету не подтверждена.»
- Plan: «По интересам / Разные форматы / Ближе к остатку»; list each event,
  showtime, catalogue price, total and calculated remainder.
- Variable price: «Итого от … ₽; расчётный остаток до … ₽. Проверь цену и наличие
  билетов у продавца.» The plan might exceed the budget at the actual seat prices.
- Empty result: «План из 2–3 событий под эти условия не получился. Можно посмотреть
  отдельные события или обновить остаток.»
- Synthetic data: «Это тестовые события, покупка недоступна.»

Copy for future features, **not implemented**:

- Optional anchor: «Есть фильм, книга или игра, к которым хочется найти что-то
  похожее?» [Указать] [Пропустить]. Use only a curated, defensible connection.
- Anchor explanation template: «Ты выбрал [тему]. В описании этого события есть
  [проверенный мотив]. Возможно, тебе подойдёт». Never fill this from imagination.
- Reminder opt-in: «Напомнить проверить остаток до конца года?» [Да] [Не надо].
- Reminder: «Последний указанный остаток — [сумма] ₽, от [дата]. Он ещё актуален?
  До конца года [N] дней». [Подобрать] [Обновить] [Отключить напоминания].

## What we deliberately do not claim

- «Кино тратится само, умирают остальные 3 000 ₽». A regional spending share does
  not measure individual cap usage or expired balances.
- «Два кошелька: кино и всё остальное». It is one balance plus a cinema restriction.
- «22% реальных событий — школьные». That share currently belongs to a synthetic
  fixture; no reproducible real-catalogue measurement accompanies it.
- «Интересных скрытых событий нет». Eligible events may be unfamiliar to users.
- «Мы единственные / аналогов нет / Госуслуги ничего не умеют». A comparative user
  task is needed before making a superiority claim.
- «Для рекомендаций всегда нужно 20 взаимодействий». No universal threshold has
  been established here. Our current choice follows our available data and deadline.
- «На карте сейчас …» without a user-report date, or «куплено» after a link click.
- «Тот же мир» for unrelated works; exact prices/dates without a checked event source.

## Defence answers

**How does this differ from another listing?**
«Мы проверяем, помогает ли подбор с учётом остатка и времени быстрее выбрать
подходящий план. В демо показываем расчёт и изменение выдачи после ответов пользователя».

**Why synthetic data?**
«На ней воспроизводимо проверяем механику. Она не доказывает качество реальной афиши
или рост посещаемости. Следующий этап — проверенный каталог и пользовательские задания».

**Why Python?**
«На Python уже реализованы диалог, фильтры, ранжирование и хранение. MAX подключается
через REST API; веб-интерфейс при необходимости добавляется отдельно».

**How will you measure benefit?**
«Время до выбора подходящего варианта, доля завершивших подбор, сохранение плана и
реальные переходы к продавцу. Покупки и посещение пока не наблюдаем».
