# Emotional anchoring: why someone actually goes

Design note. Status: proposed. Research-backed, not yet built.

## The hypothesis

Stated in our own words: *two people looking at the same event listing are not equally
likely to go. Someone who has just been absorbed in a story and wants more of that world
will go. Someone with no such pull will not, no matter how good the listing is.*

The claim is that **motivational state predicts attendance better than stated genre
preference does.** It turns out this is a well-studied effect with a name, and it has a
direct technical use for us.

---

## 1. The research says this is real

The mechanism is **narrative transportation** — being absorbed into a story world — and
**character identification**.

What the literature establishes:

- Transportation, identification with specific characters, and emotion each contribute
  to shifts in **knowledge, attitudes and behavioural intention**. It is not just a
  feeling; it moves what people intend to do.
- Character identification, perceived verisimilitude and cultural familiarity all
  increase transportation. Culturally familiar characters produce the strongest
  identification and the strongest emotions.
- Critically for product design: **transportation requires an entry point into the
  story — identification with a character, or narrative self-referencing.**

That last point is the whole design brief in one sentence. Our product's job is to
**be the entry point**, or to attach itself to one the user already has.

## 2. The effect is measurable at market scale

The January 2024 film adaptation of *Мастер и Маргарита*:

| Channel | Change after release |
|---|---|
| Читай-город / Буквоед (print) | **×4.9** |
| Республика | ×4.6 |
| Москва | ×7 in copies, ×10 in money |
| Wildberries | ×6 in purchases, ×7.7 in revenue |
| Литрес | ×4 |
| Букмейт | ×9 |
| Строки | **×50** |

Reported alongside this: **a rise in interest in Bulgakov-themed excursions in Moscow.**
That is the part that matters to us — the spillover did not stop at the book, it reached
a bookable cultural experience.

Locally, and much more on the nose for a Kazan pilot: *Слово пацана. Кровь на асфальте*
generated an entire excursion industry in Kazan — «Криминальная Казань», «Казанский
феномен», walking tours ending at the Museum of Socialist Daily Life, sold across
Yandex Afisha, Kassir, RZD Travel and independent guides.

A series created demand for a *place*. That is our mechanism, demonstrated in our pilot
city.

**Two honest caveats**, which belong in the presentation rather than being quietly
dropped:

1. These are **market-level** effects. They prove the mechanism exists across a
   population. They do not prove we can predict any individual's behaviour.
2. The *Слово пацана* excursions are **18+ and commercial — not Pushkin Card eligible.**
   Perfect as an illustration, useless as a product example. If we demo this idea, the
   bridge must land on an event the card can actually pay for.

## 3. The technical finding that makes this worth building

From the affective recommender systems literature, the single most useful sentence we
found:

> **Mood features significantly enhanced predictive accuracy, especially in cold-start
> scenarios, whereas emotions were found to introduce noise due to their transient
> nature.**

Read that against our situation. Our biggest weakness is cold start — roughly 1.8
tickets per cardholder per year, perishable inventory, no usable collaborative
signal. Mood is reported to help **most** exactly where we are **weakest**.

And the corollary is a warning: do not try to detect momentary emotion. It is noise.
Ask about mood and intent for the session, which is stable over hours.

Also useful: mood-based conversational onboarding "encourages richer, more sincere
feedback without forcing users into mechanical rating tasks." A 16-year-old will
abandon a genre checklist. They will answer "what did you watch recently that got you."

---

## 4. Three different things, which we should not conflate

The hypothesis as stated mixes three mechanisms with different lifetimes. They need
different treatment.

### (a) The anchor — durable, weeks to months

A specific work the user is currently absorbed in. *Война и мир*, *Слово пацана*,
an album, a game, a book.

- **Lifetime:** weeks.
- **How we get it:** ask, once, in onboarding.
- **What it gives us:** a rich, high-confidence taste vector from a *single answer* —
  which is exactly what a cold-start system needs.

This is the strongest signal available to us, and it costs one question.

### (b) The mood — situational, hours

What they want *tonight*: to cry, to be amazed, to not be alone, to look smart, to kill
two hours before a train.

- **Lifetime:** one session.
- **How we get it:** one tap at the start of a session.
- **What it gives us:** re-ranks the same candidate set completely. Per the research,
  this is the part that lifts cold-start accuracy.

### (c) The event's own emotional register — a property of the catalogue

How an event *feels*: devastating, funny, beautiful, weird, calming, impressive.

The API gives us **topical** tags — `Классика`, `Драма`, `История`, `Живопись`. It gives
us nothing at all about affect. We have to derive this ourselves, offline, from title and
description.

This is real work and it is the part **no competitor has**. Yandex Afisha has ratings;
nobody has "this one will wreck you."

---

## 5. How to actually use it

### The onboarding question

Replace the genre checklist. Ask instead:

> «Что ты недавно смотрел, читал или слушал, что реально зацепило?»

Free text, with a few tappable suggestions for people who freeze. Then:

1. Resolve the answer to a known work where we can (a small curated dictionary of
   popular anchors → themes, plus an LLM fallback for the long tail).
2. Map to a theme + affect vector.
3. Seed the user vector from it immediately.

One answer, and the first recommendation is already personal. Compare to a genre
checklist, which is both more work for the user and less informative.

### The bridge, and saying it out loud

This is the product moment. Do not just rank differently — **show the connection**:

> «Ты смотрела „Войну и мир“ — у Качалова идёт „Женитьба“. Тот же мир, те же люди,
> только смешно. 300 ₽, суббота в 18:00.»

Delivered flatly. The register rules in [tone.md](tone.md) apply here more than
anywhere else in the product: this is our strongest feature and our biggest cringe
risk in the same sentence.

The explanation is not decoration. Per the research, transportation needs an entry
point, and naming the bridge *is* the entry point. It is also what the brief demands —
separating fact, calculation and recommendation so the user knows where a result came
from.

### The mood tap

At the start of a session, one row of options: `что-то сильное` · `что-нибудь смешное` ·
`что-то необычное` · `красиво` · `пойти с кем-то` · `недолго, рядом`.

> An earlier draft of this list used slangier labels. See [tone.md](tone.md), Rule 6 —
> imitating how a teenager talks is the fastest way to lose one.

These map to affect axes and re-rank the candidate set. Cheap to build, immediately
visible, and it makes the product feel like it understands something the official app
does not.

### The cultural moment calendar

A major adaptation or release opens a window of elevated demand for anything connected
to it. We can prepare for this rather than react:

- track upcoming releases,
- pre-map each to card-eligible events in Kazan,
- push a proactive message in MAX when the window opens.

Proactive notification is also a MAX capability beyond the minimum, creating genuine
user value and working end to end — which is the exact shape of the **+0.15 platform
bonus**. Worth evaluating seriously once we confirm MAX supports proactive sends.

---

## 6. Deriving the affect labels

We need an affect vector per event, and the API will not give it to us. Proposal:

Offline, once per event, from `name` + `shortDescription` + `description` + `tags`,
score each event on a small fixed set of axes:

| Axis | Low ←→ High |
|---|---|
| intensity | calm ←→ overwhelming |
| valence | heavy ←→ light |
| novelty | familiar ←→ strange |
| social | solitary ←→ shared |
| effort | passive ←→ participatory |
| prestige | casual ←→ "I'd post about this" |

Five or six axes is enough and stays interpretable, which matters when a jury asks why
something was recommended.

An LLM does this labelling well and it is a legitimate use — we are classifying
descriptive text, not asserting official facts about the program's rules. Run it once
offline, cache the result, spot-check by hand. Card limits and eligibility stay in
config with a source link, as before.

Cost note: ~1,100 events × one short classification call is trivial and runs in minutes.
Re-run only for newly appearing events.

---

## 7. What this does not solve

Worth being clear-eyed, because this idea is seductive.

- **We cannot verify attendance.** Purchases happen on the external `saleLink`. The
  hypothesis is specifically about *actually going*, and that is the one thing we will
  never observe. Our best proxy is the tap-through to buy. Say so rather than implying
  we measured attendance.
- **Anchors go stale.** Someone's anchor from two months ago may be dead. Decay it, and
  re-ask occasionally.
- **Not everyone has an anchor**, and that is fine. Those users get the standard flow —
  filters, taste vector, diversity. The anchor is an accelerator, not a gate. We do not
  need to guess who is "the type to go"; we let people self-select by answering.
- **Thin catalogue risk.** If someone's anchor is anime or hip-hop, Kazan's card-eligible
  catalogue may genuinely have nothing close. The bridge must degrade honestly —
  "прямого совпадения нет, но вот что близко по ощущению" — rather than forcing a bad
  match. A dishonest bridge destroys trust faster than no bridge.

## 8. What to test first

Cheapest useful experiment, runnable inside the survey we already planned:

Show 20 people aged 14–22 two versions of the same recommendation for the same event —
one bare ("Спектакль «Женитьба», Качалов, 300 ₽, сб 18:00"), one bridged ("ты смотрела
«Войну и мир» — тот же мир, только смешно…"). Ask which one they would actually tap.

If the bridged version does not win clearly, this whole section is a nice theory and we
should spend the week elsewhere.

## Sources

- [Narrative transportation, identification and emotion shift knowledge, attitudes and behavioural intentions](https://pubmed.ncbi.nlm.nih.gov/24347679/)
- [Character identification is predicted by narrative transportation and immersive tendencies](https://www.researchgate.net/publication/359661700_Character_identification_is_predicted_by_narrative_transportation_immersive_tendencies_and_interactivity)
- [Green & Appel, Narrative Transportation: how stories shape how we see ourselves and the world (2024)](https://www.mcm.uni-wuerzburg.de/fileadmin/06110300/2024/Pdfs/Green___Appel__2024__Advances_Preprint.pdf)
- [A Survey of Affective Recommender Systems: modeling attitudes, emotions and moods](https://arxiv.org/pdf/2508.20289)
- [Мастер и Маргарита: book sales up ×5–7 after the film, Vedomosti](https://www.vedomosti.ru/media/articles/2024/02/07/1018857-premera-novoi-ekranizatsii-mastera-i-margariti-podstegnula-prodazhi-etogo-romana)
- [Same, with the per-retailer breakdown, AdIndex](https://adindex.ru/news/tendencies/2024/02/7/320328.phtml)
- [«Криминальная Казань: Казанский феномен. Слово пацана» excursions, Yandex Afisha](https://afisha.yandex.ru/kazan/excursions/kriminalnaya-kazan-kazanskiy-fenomen-slovo-patsana-18)
- Related: [ranking.md](ranking.md), [hypothesis-boring-events.md](../research/hypothesis-boring-events.md)
