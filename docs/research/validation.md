# Research review and validation protocol

Reviewed: 25 September 2026. Status: desk review complete for the claims below;
interviews, controlled comparisons, live catalogue checks and MAX device tests have
**not** been conducted by this review. Do not turn planned research into results.

This note corrects earlier inferences in `pushkin-card`, `hypothesis-boring-events`,
`ranking`, `tone` and `emotional-anchors`. Those are exploratory design notes, not an
independent chain of evidence: one citing another does not validate a claim.

## Evidence register

| Claim | Evidence / provenance | Verdict and permitted wording |
|---|---|---|
| 2026 annual limit 5,000 RUB, including up to 2,000 on cinema | Official [Культура.РФ programme page](https://www.culture.ru/pushkinskaya-karta), [VTB product page](https://www.vtb.ru/personal/karty/debetovye/pushkinskaya_karta/); current indexed official content checked on review date | Use as current configuration, with source/date; verify again before launch. A reported draft for 7,000 is not an enacted rule |
| Cinema accounts for about 40% of spending | [Sib.fm, 27 July 2026, citing VTB](https://sib.fm/news/2026/07/27/vtb-naibolee-aktivno-pushkinskuyu-kartu-oformlyayut-starsheklassniki): Novosibirsk regional spending, not nationwide expired balances | May describe that regional expenditure mix. Cannot infer that every user uses the cinema cap or loses 3,000 RUB |
| 55% are aged 15–18 | Same regional publication | Keep regional scope; not enough to state a nationwide median age or define all users as schoolchildren |
| 1.8 tickets per holder per year, 7.3m cards / 13m tickets in nine months | The ranking note links the July article above, which does not supply these numbers | Remove from product argument until matching original reporting and periods are found; purchases also differ from recommendation interactions |
| 22% of Kazan events are organised school visits | `data/README.md` describes this mix in a generated fixture, while claiming inspiration from observations | Synthetic benchmark composition, not a measured population statistic. Require saved source records, sampling rule and labels before a real share is quoted |
| About 240 eligible events on one Sunday | Team note estimates pages × 20 from a 23 September listing; no archived dataset is included | Preliminary observation only; distinguish unique events, venues and showtimes. Not proof of choice overload |
| 40,593 unused cards / 367m RUB | Historical [ПроВладимир publication](https://provladimir.ru/2026/02/20/teatry-i-muzei-lidiruyut-u-vladelczev-pushkinskoj-karty/), published 20 Feb 2026, reporting April 2023 data | Historical secondary-source context only. Not annual expired funds, not a 2026 measurement, not our pilot outcome |
| No balance integration | Code asks the user; no integration available to this project | Say «остаток вводится пользователем». Avoid claiming to have proved that no private/partner integration could exist |
| No competitor answers this task | No reproducible cross-product study in the repository | A differentiating hypothesis, not a verified exclusivity claim |
| Neutral copy, explanations, anchors improve outcomes | Design literature and examples motivate hypotheses; no local user results | Test them. Do not promise better conversion or immunity to reactance/manipulation |

For the official rules, direct page retrieval timed out during this review; the
official pages' indexed content was accessible. Keep this verification limit visible
instead of implying a fresh bank/API integration. No legal interpretation of drafts
or disputed eligibility categories is added here.

## Additional checks of the psychology sources

- [SKIM's original report](https://skimgroup.com/blog/the-authenticity-gap-what-gen-z-really-thinks-about-your-brand/)
  describes **543 people aged 18–25 in eight countries, none of them Russia**, using
  its QualBot qualitative research framework. It reports 44% mentioning transparency
  and 32% forced communication. This is contextual evidence about brands, not a
  validated wording rule for Russian 15–18-year-olds. The earlier “20% unfollowed”
  row is not supported by that report and should not be attributed to it.
- [Hasan & Bunescu's 2025 survey](https://arxiv.org/html/2508.20289v1) does discuss
  mood-aware recommendations. The particular cold-start/mood-versus-emotion finding
  cited in `emotional-anchors.md` refers to Piazza et al. (2017), a study of **fashion
  product preferences**, not cultural-event attendance. It motivates an experiment;
  it does not prove that our six mood buttons improve recommendations. The survey
  also covers emotion-aware systems, so “emotions are always noise” is unjustified.
- The PubMed source linked in the earlier note presented a browser verification
  screen during this review. Its full findings were not revalidated here. Retain it
  as a literature lead, not as evidence that our proposed anchor improves attendance.

## Correct budget model

Let B be the self-reported total remaining balance and C the remaining cinema
allowance, bounded by B and the annual cinema cap. A plan must satisfy:

```text
sum(all ticket prices) <= B
sum(cinema ticket prices) <= C
```

Non-cinema events can use the entire B. Do not subtract the cinema cap from it.
Unknown B permits browsing but no claim of a funded plan; unknown C excludes cinema
until clarified. Selecting a plan or opening a seller link does not debit B.
Catalogue `price` may mean a minimum price: calculate a provisional plan and disclose
that current seat prices/availability can invalidate it.

## What we recommend building and testing

Keep the existing Python bot, profile store, ranking and reproducible fixture.
Add budget plans as a bounded module; this branch implements that module and chat
entry point. Use a compact real snapshot for user testing once its source records
are checked. The synthetic fixture remains useful for regressions and scale tests.

An optional cultural anchor and session feedback are promising additions. Do not
require 20 swipes or a free-text cultural answer before showing value. Compare the
current five-card quiz against a skippable/shorter path. Being interested in one work
does not make every loosely related event relevant.

The current keyword audience classifier is a heuristic: a 0+/6+ show is not necessarily
for small children, and a puppet theatre can stage adult work. Measure false exclusions
on independent real records before making it a product advantage or a hard gate.

## Interviews: ready to run, no results yet

Recruit 20–40 Kazan cardholders if feasible, with a smaller 5-person usability round
first. Include both people who spent most of the balance and people who did not;
recruiting only dissatisfied users would bias the conclusion. Proposed primary segment
15–18; include a small 19–22 comparison group. Do not collect names, card details,
account screenshots, school names or exact home addresses for this study.

Russian questions, asked before showing the product:

1. «Расскажи, как ты в последний раз выбирал(а) событие по Пушкинской карте.
   Где искал(а), что выбрал(а), что было неудобно?»
2. «Когда пользовался(ась) картой последний раз? На что? Если не пользовался(ась),
   что остановило?» Do not suggest forgetting or boring events first.
3. «Знаешь ли текущий остаток и сколько ещё доступно на кино?» Accept “don't know”;
   use an invented task balance for the experiment if the participant prefers.
4. «Был ли остаток в конце прошлого года? Что помешало его использовать?»
   Self-report, not verified financial history; “don't remember” is a valid answer.
5. «Когда тебе удобно ходить и сколько времени готов(а) тратить на дорогу?»
6. «Покажи, как обычно выбираешь между несколькими вариантами. Что заставляет
   отказаться даже от интересного события?»

Record anonymised participant code, age band, prior card use, task observations,
exact optional quotes and counterexamples. Keep researcher inference in a separate
column. Obtain voluntary agreement, allow skipping/stopping, follow organiser rules
for research with minors. Report recruitment method and sample limits.

## Controlled tasks

**A. Does a plan help?** Give the same checked eligible catalogue and a fixed scenario
(e.g. B=3,000, C=0, selected free slots) to a listing and to the planner. Alternate
which interface is seen first; use comparable tasks to reduce learning effects.
Measure time to an acceptable choice, completion, budget/schedule mistakes and
participant-rated willingness to go. A near-zero remainder is secondary to suitability.

**B. Does an explanation help?** Same event, image, price, position and date; change
only the presence of a truthful reason. Alternate presentation order. Measure choice
and comprehension, and ask what felt inaccurate. A preference in a small convenience
sample is exploratory, not evidence of population-level purchase uplift.

**C. Is the anchor worth a question?** Compare an optional curated anchor to simple
interest choices. Measure abandonment, time to first useful result and relevance.
Record unmatched answers rather than inventing associations.

**D. Reminders.** When implemented, collect explicit opt-in, offer cancellation and
compare consenting groups with/without reminders over the same period. Without that
follow-up, only measure comprehension and willingness to opt in, not spending effect.

Proposed internal decision gates, not industry standards: first five testers should
complete the core task without critical help; no invalid budget/schedule plans in
test cases; log every false audience exclusion. Rework failure points before expanding
the catalogue or claiming wins. Report raw counts alongside percentages.

## Measurement contract

| Metric | Definition / instrument | Current status |
|---|---|---|
| Time to useful result | Start to participant-confirmed acceptable event/plan | Manual usability measurement; no automated “useful” label |
| Plan choice rate | Explicitly selected plans / sessions shown a feasible plan | UI opens plan details; explicit firm-choice action/event still pending; opening is not selecting |
| Seller click rate | Observed seller-link clicks / event cards shown | Not yet instrumented; typing an event title must not count |
| Planned utilisation | Sum of selected quoted prices / reported B | Estimate only; neither actual spend nor annual utilisation |
| Reminder opt-in | Explicit consent / eligible users offered reminders | Scheduler and explicit consent implemented 26 Sep; no measured live delivery or opt-in rate yet |
| Purchase / attendance | Verified partner feedback or explicitly labelled self-report | Unobserved; cannot use clicks as purchases |

Do not compare a self-selected pilot's planned spending with a national annual average
as if it were a causal effect. Use comparable tasks or a consented controlled pilot.

## Data and competitor checks to finish with the team

- Real snapshot: save source URL, event ID, retrieval time, city, eligibility evidence,
  price range, each showtime/duration, venue and seller URL. Recheck before the demo.
- Deduplicate by event ID; count showtimes separately. Annotate a random sample with
  two people where possible; don't use synthetic generator labels as real-world truth.
- Compare Gosuslugi Культура, Культура.РФ and a ticket aggregator using the same Kazan
  date/budget task. Record platform version, date, steps/time and screenshots obtained
  with permission. Mark untested functionality “unknown”, not “absent”.
- ProCulture integration needs the team's key and a confirmed city filter. The adapter
  is code, not proof of access, full coverage, availability or production readiness.
- A second-city pilot needs source coverage, time zone, local quality checks, hosting,
  token/organisation access and operational ownership. Changing a city string is not
  sufficient evidence of scaling.

Deliverables completed here: corrected claim register, product copy, interview guide,
comparison protocol, metric definitions and implementation/audit links. Remaining
field work above must be reported as pending until actually performed.
