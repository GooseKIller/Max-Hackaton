# Testing the hypothesis: "the events on the card are boring"

Status: checked 23 September 2026, against live data for Kazan.

## The hypothesis we started with

> The events offered by Gosuslugi Kultura are bad. Teenagers don't want classic theatre
> with fairy tales. The main holders are 14–18. Meanwhile the city is full of cool
> events that the official app doesn't show, or shows badly. We should find those events
> and give them to people.

Three separate claims. We checked each one.

---

## Claim 1: "The main holders are 14–18" — CONFIRMED

**Fact.** VTB reports that **55% of all cardholders are aged 15–18**.
Ministry-level statements name **17 years old** as the core age of the program.
Media reports identify 15–17 year olds as the most active users.

So: the median user is a **high school student**, not a university student. Our product
should be designed for a 16-year-old, not a 21-year-old.

**Second useful number from the same source:** in one region, about **40% of all card
money went to cinema** — that is, users push the 2,000 RUB cinema sub-limit to its cap.

This tells us where the money actually dies. Cinema money gets spent easily; it is the
remaining **3,000 RUB of "everything else"** that people struggle to use. That is the
part of the budget our product should fight for.

---

## Claim 2: "Cool events exist in the city that aren't on the card" — MOSTLY WRONG, AND IT MATTERS

This is the part of the hypothesis we should drop, because building on it would produce
a product that cannot actually spend the card.

**Fact.** The Pushkin Card is a closed program. An event can be paid for with the card
only if:

1. The organisation is registered on PRO.Культура.РФ and accepted into the program, and
2. The event passes **two stages of moderation** — platform specialists, then an
   **Expert Council** that checks it against the program's rules.

**Fact.** Since 2024 the selection criteria explicitly require events to align with the
state policy on "preserving and strengthening traditional Russian spiritual and moral
values" (Presidential Decree of 9 November 2022).

**Fact.** Concerts by popular performers and entertainment shows are **not** eligible.
Free events are not eligible either — a price is mandatory. Bundling extras (transport,
food, tastings, photo sessions, souvenirs) into a card ticket is forbidden and gets the
event thrown out of the program.

**What this means.** A cool underground gig, a stand-up night, or a commercial party is
not "poorly shown by Gosuslugi Kultura." It is **outside the program entirely** and no
amount of discovery work will let the card pay for it. If we surface those events, we
have built a general city guide that does not solve the card problem.

→ We can still *mention* non-card events as a secondary layer later, but they cannot be
the core of the product.

---

## Claim 3: "The events shown are boring / badly shown" — RIGHT, BUT THE CAUSE IS DIFFERENT

The instinct is correct. The cause is not bad supply. It is **bad ranking and bad
filtering on top of good supply.**

### Kazan has plenty of events

Measured on culture.ru's Kazan Pushkin Card listing on 23 September 2026:

| Slice | Pages | Approx. events (20/page) |
|---|---|---|
| All upcoming | 55 | **~1,100** |
| One single Sunday (27 Sept) | 12 | **~240** |
| Same Sunday, filtered "Для молодежи" | 7 | **~140** |

Supply is not the problem. **A teenager in Kazan has roughly 240 options on a single
Sunday.** That is a choice-overload problem, not a scarcity problem.

### But the listing is chronological, not relevant

The official listing is ordered by date. There is no ranking, no personalisation, no
notion of what this particular user likes.

### And the filtering is actively broken

On 27 September, with the **"Для молодежи"** (for youth) filter switched on, the results
still included:

- **«Программа "Беби-концерт"»** — a concert for babies
- **«Старик из деревни Альдермеш»**

Meanwhile the unfiltered Sunday list is full of `Бэби-спектакль «Приключения пингвиненка
Пинка»`, `«Гуси-лебеди»`, `«Воробьишко»`, `«Про кота и про любовь»` — puppet theatre for
small children, sitting in the same flat list a 16-year-old has to scroll through.

This is the concrete, demonstrable failure. **A baby concert shows up under "for youth".**

It is worse than it looks, because the underlying data is fine: every event in the
PRO.Культура.РФ API carries an `ageRestriction` field. The official surface simply does
not use it to decide relevance.

### Another structural problem: the events are scheduled for school groups, not for teenagers

Looking at weekday listings, a large share of events start at **09:00, 10:00, 12:00,
15:00 on weekdays**, hosted at lyceums, libraries and colleges. These are organised
school excursions — bulk-booked by a teacher, not chosen by a kid.

For a teenager deciding for themselves, most of the nominal supply is at a time they are
in class. Filtering to "when I am actually free" collapses the list dramatically — and
no existing tool does this.

### The genuinely interesting events are in there, just buried

From the same Kazan listing, all payable by the card:

- **«Ток бежит по проводам»** — an industrial tour of a power engineering university
- **Иммерсивный спектакль «Лёгкий человек»**
- **Интеллектуальная игра по французскому искусству** at the Khazine gallery
- **«Как смотреть танцевальный спектакль?»** at the Kamal Theatre
- **Экскурсия и мастер-класс по валянию** at the Spasskaya Tower Museum
- **Квартирник «Школьная пора»**
- **«Кара Карамазовых»** at the Kachalov Theatre

None of these are "classic theatre with fairy tales." They are buried under hundreds of
chronologically-sorted entries, most of which are for a different audience entirely.

**This is good news for us.** It means our product can be built entirely on official
data from a primary source, which is exactly what the brief rewards — instead of
scraping events the card cannot pay for anyway.

---

## The competitive picture is wider than we assumed

Gosuslugi Kultura is not the only window into card events. Kazan Pushkin Card listings
also exist on **Yandex Afisha**, **Kassir**, **MTS Live** and **Ticketland**.

Yandex Afisha's Kazan card section is noticeably better than the official one: events
are grouped by type, carry user ratings (8.5, 9.3, …), and there is a "popular" block.

But it has two structural gaps:

1. **It only shows what its ticketing partners sell** — commercial theatre, concerts,
   musicals. The museum, excursion, lecture and workshop long tail is missing. This is
   the smaller, more commercial slice of the ~1,100.
2. **It knows nothing about the card itself** — not your balance, not the cinema
   sub-limit, not the 31 December expiry.

| | Full official supply | Good ranking | Knows your taste | Knows your balance & deadline |
|---|---|---|---|---|
| Gosuslugi Kultura / culture.ru | yes | no | no | balance only, in-app |
| Yandex Afisha / Kassir / MTS Live | no (commercial slice) | yes | partly | no |
| **Us** | yes (via API) | yes | yes | yes (user-reported) |

---

## Where this leaves the product idea

The reframing:

> We are not finding events that are hidden from the program.
> We are **ranking the events that are already in the program, for a specific teenager,
> against a specific remaining balance and a deadline.**

The job to be done, stated as a user would: *"I'm 16, I have 3,200 RUB left that expires
on 31 December, I'm free on Saturday afternoon, I live near Гагарина — what should I
actually go to?"*

No existing tool answers that question. The official one has all the data and none of
the relevance; the commercial ones have the relevance and neither the full catalogue nor
the card context.

Concrete things we can do that nobody does:

1. **Filter by real age fit**, using `ageRestriction` plus our own signals — so baby
   concerts never reach a 16-year-old.
2. **Filter by when a teenager is actually free** — evenings and weekends, not 10:00 on
   a Tuesday.
3. **Learn taste** from a short quiz plus what they click, and rank accordingly.
4. **Plan the budget** — two pools (cinema and everything else) against days remaining.
5. **Remind before the money burns**, in a messenger they already have open.
6. **Surface the long tail** — the power plant tour, the felting workshop, the immersive
   show — which is the part that makes the product feel non-boring.

## What still needs checking

- [ ] Get the PRO.Культура.РФ API key and **count precisely**: how many Kazan events,
      how many after an age filter, how many in evening/weekend slots. The numbers above
      are page-count estimates from the public site and should be replaced with exact
      figures from the API. These counts are our strongest evidence slide.
- [ ] Check whether `ageRestriction` is populated reliably, or often defaults to 0/6.
- [ ] Verify the claim that pop concerts are banned against the actual government
      decree (Постановление № 1521), not media summaries.
- [ ] Find out whether teenagers even know the non-cinema money exists as a separate
      pool. This is a survey question.

## Sources

- [VTB: 55% of cardholders are aged 15–18](https://sib.fm/news/2026/07/27/vtb-naibolee-aktivno-pushkinskuyu-kartu-oformlyayut-starsheklassniki)
- [Golikova on the core age of cardholders](https://portal-kultura.ru/articles/news/378584-golikova-nazvala-osnovnoy-vozrast-derzhateley-pushkinskoy-karty/)
- [Teenagers 15–17 are the most active users](https://dag.aif.ru/society/samymi-aktivnymi-polzovatelyami-pushkinskoy-karty-stali-podrostki-15-17-let)
- [PRO.Культура.РФ: how to register events for the program](https://pro.culture.ru/blog/653)
- [PRO.Культура.РФ: five cards on creating Pushkin Card events](https://pro.culture.ru/blog/820)
- [Expanded requirements for organisers, RBC, Feb 2024](https://www.rbc.ru/society/23/02/2024/65d7b9899a7947c860d4f146)
- [Government resolution No. 1521 of 08.09.2021](http://government.ru/docs/all/136439/)
- [Kazan Pushkin Card listing, Культура.РФ](https://www.culture.ru/afisha/kazan/pushkinskaya-karta)
- [Kazan Pushkin Card listing, Yandex Afisha](https://afisha.yandex.ru/kazan/pushkin-card)
