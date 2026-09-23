"""
Generate a synthetic Kazan event catalogue in the PRO.Культура.РФ API 2.5 schema.

THIS IS NOT REAL DATA. Every event here is generated. Venue names are real Kazan
institutions, used so the catalogue reads plausibly to someone who knows the city,
but no event, date, price or ticket link is real.

Why this exists: the PRO.Культура.РФ integration key is a partnership request with an
unknown lead time, and we have a week. This generator lets us build and demo the whole
pipeline now, and swap in the real feed later without touching anything above the
data layer.

Why it is shaped the way it is: our product's claim is that the official listing mixes
baby concerts, school-group excursions and genuinely interesting events into one flat
chronological list. If we generated uniformly random events, our ranking would have
nothing to fix and the demo would prove nothing. So this generator deliberately
reproduces the distribution we measured on the live culture.ru listing for Kazan:

    ~50%  events a teenager cannot or would not attend
          (small children, and weekday-daytime organised school groups)
    ~35%  mainstream classic theatre and classical concerts
    ~15%  the long tail that makes the product feel non-boring
          (industrial tours, immersive theatre, workshops, quizzes, lectures)

Run:  python3 data/generate_fixtures.py
Out:  data/kazan_events.json
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261029  # the final, in Kazan. Fixed so the dataset is reproducible.
OUT = Path(__file__).parent / "kazan_events.json"

TOTAL_EVENTS = 1100  # matches what we counted on the live Kazan listing
CATALOGUE_START = datetime(2026, 9, 24, tzinfo=timezone.utc)
CATALOGUE_DAYS = 98  # roughly to the end of the year, when the balance expires

KAZAN_TZ = "Europe/Moscow"
KAZAN_LOCALE = {
    "_id": 78,
    "sysName": "kazan",
    "name": "Казань",
    "timezone": KAZAN_TZ,
    "isYandexExport": True,
}
REGION = {
    "name": "Татарстан",
    "type": "Респ",
    "fiasId": "0c089b04-099e-4e0e-955a-6bf1ce525f1a",
    "isPostfix": False,
}
CITY = {
    "name": "Казань",
    "type": "г",
    "fiasId": "93b3df57-4c89-44df-ac42-96f05e9cd3b9",
}

# Real Kazan institutions. Coordinates are approximate city-centre positions —
# good enough for distance ranking, not survey-grade.
VENUES = [
    # (name, place category, lat, lon, street, house)
    ("Казанский государственный академический русский драматический театр им. В. И. Качалова", "teatry", 55.7903, 49.1180, "Баумана", "48"),
    ("Татарский государственный академический театр им. Г. Камала", "teatry", 55.7793, 49.1246, "Татарстан", "1"),
    ("Татарский государственный академический театр кукол «Экият»", "teatry", 55.7723, 49.1301, "Петербургская", "57"),
    ("Татарский государственный театр драмы и комедии им. К. Тинчурина", "teatry", 55.7869, 49.1222, "Горького", "13"),
    ("Казанский государственный театр юного зрителя на ул. Островского", "teatry", 55.7887, 49.1153, "Островского", "10"),
    ("Казанский татарский государственный театр юного зрителя им. Габдуллы Кариева", "teatry", 55.7846, 49.1268, "Петербургская", "55"),
    ("Театр на Булаке", "teatry", 55.7837, 49.1191, "Право-Булачная", "47"),
    ("Учебный театр г. Казань", "teatry", 55.7921, 49.1224, "Пушкина", "86"),
    ("Татарская государственная филармония им. Г. Тукая", "koncertnye-ploshchadki", 55.7930, 49.1235, "Павлюхина", "73"),
    ("Государственный Большой концертный зал им. С. Сайдашева", "koncertnye-ploshchadki", 55.7914, 49.1224, "Пушкина", "2"),
    ("КРК «Пирамида»", "koncertnye-ploshchadki", 55.7986, 49.1063, "Московская", "70"),
    ("Государственный музей изобразительных искусств Республики Татарстан", "muzei-i-galerei", 55.7950, 49.1141, "Карла Маркса", "64"),
    ("Национальная художественная галерея «Хазинэ»", "muzei-i-galerei", 55.7989, 49.1055, "Кремль", "3"),
    ("Галерея современного искусства ГМИИ РТ", "muzei-i-galerei", 55.7952, 49.1147, "Карла Маркса", "57"),
    ("Национальный музей Республики Татарстан", "muzei-i-galerei", 55.7975, 49.1085, "Кремлёвская", "2"),
    ("Музей истории государственности татарского народа и Республики Татарстан", "muzei-i-galerei", 55.7995, 49.1050, "Кремль", "5"),
    ("Музей естественной истории Татарстана", "muzei-i-galerei", 55.7992, 49.1060, "Кремль", "2"),
    ("Музей Спасской башни", "kulturnoe-nasledie", 55.7968, 49.1078, "Кремль", "1"),
    ("Музей Салиха Сайдашева", "muzei-i-galerei", 55.7885, 49.1204, "Горького", "13"),
    ("Присутственные места", "kulturnoe-nasledie", 55.7983, 49.1062, "Кремль", "4"),
    ("Интерактивный мультимедийный комплекс «Шарык клубы»", "prochee", 55.7841, 49.1174, "Парижской Коммуны", "25"),
    ("Культурный центр им. А. С. Пушкина", "dvorcy-kultury-i-kluby", 55.7928, 49.1281, "Карла Маркса", "26"),
    ("Культурный центр им. Якова Емельянова", "dvorcy-kultury-i-kluby", 55.8127, 49.0894, "Ленинградская", "23"),
    ("Дом дружбы народов Татарстана", "dvorcy-kultury-i-kluby", 55.7772, 49.1180, "Павлюхина", "57"),
    ("Республиканская юношеская библиотека г. Казани", "biblioteki", 55.7901, 49.1350, "Декабристов", "2"),
    ("Филиал № 1 Республиканской юношеской библиотеки РТ", "biblioteki", 55.8202, 49.0781, "Копылова", "12"),
    ("Казанский государственный энергетический университет", "obrazovatelnye-uchrezhdeniya", 55.7534, 49.2054, "Красносельская", "51"),
    ("Институт «Казанская академия ветеринарной медицины»", "obrazovatelnye-uchrezhdeniya", 55.7856, 49.1615, "Сибирский тракт", "35"),
    ("Многопрофильный лицей № 11 «Унбер»", "obrazovatelnye-uchrezhdeniya", 55.8271, 49.0703, "Восстания", "36"),
    ("Центральная городская библиотека", "biblioteki", 55.7909, 49.1224, "Вишневского", "10"),
]

TAGS = {
    # id: (name, sysName)
    101: ("Классика", "klassika"),
    102: ("Современное искусство", "sovremennoe-iskusstvo"),
    103: ("Иммерсивный", "immersivnyy"),
    104: ("Танец", "tanec"),
    105: ("Наука", "nauka"),
    106: ("История", "istoriya"),
    107: ("Технологии", "tehnologii"),
    108: ("Мастер-класс", "master-klass"),
    109: ("Для детей", "dlya-detey"),
    110: ("Для молодежи", "dlya-molodezhi"),
    111: ("Татарская культура", "tatarskaya-kultura"),
    112: ("Музыка", "muzyka"),
    113: ("Живопись", "zhivopis"),
    114: ("Литература", "literatura"),
    115: ("Драма", "drama"),
    116: ("Комедия", "komediya"),
    117: ("Фотография", "fotografiya"),
    118: ("Интеллектуальная игра", "intellektualnaya-igra"),
    119: ("Архитектура", "arhitektura"),
    120: ("Этнография", "etnografiya"),
    121: ("Кино", "kino"),
    122: ("Анимация", "animaciya"),
    123: ("Экология", "ekologiya"),
    124: ("Ремесло", "remeslo"),
}

CATEGORIES = {
    "spektakli": "Спектакли",
    "koncerty": "Концерты",
    "vystavki": "Выставки",
    "ekskursii": "Экскурсии",
    "obuchenie": "Обучение",
    "vstrechi": "Встречи",
    "prazdniki": "Праздники",
    "kino": "Кино",
    "prochie": "Прочие",
}


# --- Archetypes ------------------------------------------------------------
#
# Each archetype defines a slice of the catalogue: what it is called, when it
# happens, what it costs, who it is really for. `share` sums to 1.0.
#
# `audience` is our own ground-truth label. It is NOT part of the real API
# schema and is stripped from the output — we keep it only so the generator can
# build a matching answer key (kazan_events_labels.json) to evaluate our
# audience classifier against. The real feed will not hand us this.

ARCHETYPES = [
    {
        "key": "baby",
        "share": 0.09,
        "audience": "babies",
        "titles": [
            "Бэби-спектакль «Приключения пингвинёнка Пинка»",
            "Программа «Беби-концерт»",
            "Бэби-театр «Солнечный зайчик»",
            "Музыкальная азбука от А до Я",
            "Бэби-концерт «Первые звуки»",
            "Сенсорная сказка «Тёплый дом»",
        ],
        "categories": ["spektakli", "koncerty"],
        "venue_kinds": ["teatry", "koncertnye-ploshchadki"],
        "age": [0, 0, 0, 6],
        "hours": [9, 10, 11, 12],
        "weekend_bias": 0.8,
        "price": (450, 1500),
        "tags": [109, 112],
        "blurb": "Интерактивная программа для самых маленьких зрителей и их родителей.",
    },
    {
        "key": "kids",
        "share": 0.18,
        "audience": "children",
        "titles": [
            "Спектакль «Гуси-лебеди»",
            "Спектакль «Про кота и про любовь»",
            "Спектакль «Воробьишко»",
            "Спектакль «Щенок, не умеющий лаять»",
            "Спектакль «Абугалисина»",
            "Спектакль «Кто стучит в моё окно?»",
            "Новогодняя сказка «Снежный ключ»",
            "Кукольный спектакль «Три медведя»",
        ],
        "categories": ["spektakli"],
        "venue_kinds": ["teatry"],
        "age": [0, 6, 6, 6],
        "hours": [9, 10, 11, 14],
        "weekend_bias": 0.7,
        "price": (280, 900),
        "tags": [109, 115],
        "blurb": "Спектакль для детей младшего школьного возраста по мотивам известной сказки.",
    },
    {
        "key": "school_group",
        "share": 0.23,
        "audience": "school_group",
        "titles": [
            "Интеллектуальная игра «Знатоки наук»",
            "Программа «Игры пушкинской эпохи»",
            "Концерт «Наследники традиций»",
            "Концерт «Мы разные, но мы вместе»",
            "Урок мужества «Живая память»",
            "Познавательная программа «Азбука безопасности»",
            "Тематическая программа «Мой город — моя гордость»",
            "Литературная гостиная «Строки, опалённые войной»",
            "Классный час «传统 и современность»".replace("传统", "Традиции"),
        ],
        "categories": ["vstrechi", "obuchenie", "koncerty", "prazdniki"],
        "venue_kinds": ["obrazovatelnye-uchrezhdeniya", "biblioteki", "dvorcy-kultury-i-kluby"],
        "age": [6, 12, 12],
        "hours": [9, 10, 11, 12, 13, 14, 15],
        "weekend_bias": 0.02,  # almost always a weekday — this is the tell
        "price": (150, 500),
        "tags": [106, 114, 110],
        "blurb": "Программа рассчитана на организованные группы учащихся образовательных учреждений.",
    },
    {
        "key": "classic_theatre",
        "share": 0.20,
        "audience": "general",
        "titles": [
            "Спектакль «Капитанская дочка»",
            "Спектакль «Правда – хорошо, а счастье лучше»",
            "Спектакль «Женитьба»",
            "Спектакль «Золотой телёнок»",
            "Спектакль «Человек в футляре»",
            "Спектакль «Дон Жуан»",
            "Спектакль «Безумный день, или Женитьба Фигаро»",
            "Спектакль «Укрощение строптивой»",
            "Спектакль «Дом Бургана»",
            "Спектакль «Старик из деревни Альдермеш»",
            "Спектакль «Мама приехала»",
        ],
        "categories": ["spektakli"],
        "venue_kinds": ["teatry"],
        "age": [12, 16, 16],
        "hours": [18, 18, 19],
        "weekend_bias": 0.45,
        "price": (100, 1200),
        "tags": [101, 115, 114],
        "blurb": "Постановка по классическому произведению в репертуаре театра.",
    },
    {
        "key": "classical_concert",
        "share": 0.15,
        "audience": "general",
        "titles": [
            "Концерт «Дмитрий Шостакович. К 120-летию со дня рождения»",
            "Концерт «Магия музыкального релакса»",
            "Концерт «Балалайка-кудесница, домра-затейница и другие…»",
            "Концерт «Приношение Гумилёву»",
            "Органный вечер «Свет и тень»",
            "Концерт «Голос эпохи»",
            "Вечер татарской музыки «Моң»",
        ],
        "categories": ["koncerty"],
        "venue_kinds": ["koncertnye-ploshchadki", "muzei-i-galerei"],
        "age": [6, 12, 12],
        "hours": [15, 18, 19],
        "weekend_bias": 0.4,
        "price": (300, 2200),
        "tags": [101, 112, 111],
        "blurb": "Концертная программа в исполнении артистов и творческих коллективов республики.",
    },
    {
        "key": "exhibition",
        "share": 0.07,
        "audience": "general",
        "titles": [
            "Выставка «Сады вечности»",
            "Выставка «Райский сад: искусство российского ислама»",
            "Выставка Айрата Хамидуллина",
            "Выставка «Костюмы Поволжья: образы народной культуры»",
            "Выставка «Культурный код Казани»",
            "Фотовыставка «Город, который мы не замечаем»",
        ],
        "categories": ["vystavki"],
        "venue_kinds": ["muzei-i-galerei", "kulturnoe-nasledie"],
        "age": [0, 6, 12],
        "hours": [10, 11, 12, 14, 16],
        "weekend_bias": 0.35,
        "price": (150, 500),
        "tags": [113, 102, 120, 117],
        "blurb": "Экспозиция открыта для самостоятельного посещения в часы работы музея.",
        "long_run": True,
    },
    {
        "key": "long_tail",
        "share": 0.08,
        "audience": "teen_friendly",
        "titles": [
            "Индустриальная экскурсия «Ток бежит по проводам»",
            "Иммерсивный спектакль «Лёгкий человек»",
            "Интеллектуальная игра по французскому искусству",
            "Экскурсия и мастер-класс по валянию",
            "Мастер-класс «Волшебство в движении»",
            "Квартирник «Школьная пора»",
            "Лекция «Московские и казанские коллекционеры»",
            "Спектакль «Как смотреть танцевальный спектакль?»",
            "Ночь в музее: маршрут без экскурсовода",
            "Мастер-класс по аналоговой фотографии",
            "Лаборатория современного танца: открытая репетиция",
            "Экскурсия «Казань, которой нет на открытках»",
            "Воркшоп «Как собрать свой подкаст»",
            "Медиалаборатория «Город в 16 кадрах»",
            "Экскурсия по закулисью театра",
        ],
        "categories": ["ekskursii", "obuchenie", "spektakli", "vstrechi", "prochie"],
        "venue_kinds": [
            "obrazovatelnye-uchrezhdeniya", "muzei-i-galerei", "teatry",
            "kulturnoe-nasledie", "prochee",
        ],
        "age": [12, 16, 16, 16],
        "hours": [16, 17, 18, 19],
        "weekend_bias": 0.55,
        "price": (150, 2500),
        "tags": [102, 103, 105, 107, 108, 110, 118, 124],
        "blurb": "Формат, в котором участники вовлечены в происходящее, а не просто наблюдают со стороны.",
    },
]

CINEMA_ARCHETYPE = {
    "key": "cinema",
    "share": 0.0,  # handled separately: cinema has its own budget pool
    "audience": "general",
    "titles": [
        "Показ фильма «Здесь был Юра»",
        "Показ фильма «Свет вокруг»",
        "Показ отреставрированной классики",
        "Кинопоказ с обсуждением",
        "Документальное кино о городе",
    ],
    "categories": ["kino"],
    "venue_kinds": ["prochee", "dvorcy-kultury-i-kluby"],
    "age": [6, 12, 16],
    "hours": [16, 18, 19, 20],
    "weekend_bias": 0.5,
    "price": (250, 600),
    "tags": [121, 122],
    "blurb": "Киносеанс в рамках программы «Пушкинская карта».",
}


def pick_venue(rng: random.Random, kinds: list[str]) -> tuple:
    matching = [v for v in VENUES if v[1] in kinds]
    return rng.choice(matching or VENUES)


def make_address(street: str, house: str) -> dict:
    return {
        "region": REGION,
        "city": CITY,
        "street": {
            "name": street,
            "type": "ул",
            "fiasId": f"synthetic-street-{abs(hash(street)) % 10**8:08d}",
            "isPostfix": False,
        },
        "house": {
            "name": house,
            "type": "д",
            "fiasId": f"synthetic-house-{abs(hash(street + house)) % 10**8:08d}",
        },
    }


def make_seances(rng: random.Random, arch: dict) -> list[dict]:
    """Build the list of showtimes for one event."""
    if arch.get("long_run"):
        # An exhibition runs daily for weeks. Model it as one long span.
        start_day = rng.randrange(0, CATALOGUE_DAYS - 20)
        length = rng.randrange(14, 60)
        starts = [start_day + d for d in range(0, length, max(1, length // 12))]
    else:
        count = rng.choice([1, 1, 1, 2, 2, 3, 4])
        starts = rng.sample(range(CATALOGUE_DAYS), min(count, CATALOGUE_DAYS))

    seances = []
    for day_offset in sorted(starts):
        day = CATALOGUE_START + timedelta(days=day_offset)
        is_weekend = day.weekday() >= 5

        # weekend_bias decides how likely this archetype is to land on a weekend.
        # Re-roll the day once if it fell on the wrong kind of day.
        if rng.random() > arch["weekend_bias"] and is_weekend:
            day -= timedelta(days=rng.randrange(1, 4))
        elif rng.random() < arch["weekend_bias"] and not is_weekend:
            day += timedelta(days=(5 - day.weekday()) % 7)

        hour = rng.choice(arch["hours"])
        minute = rng.choice([0, 0, 30])
        start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        duration = timedelta(minutes=rng.choice([60, 90, 120, 150, 180]))
        end = start + duration

        seances.append({
            "start": int(start.timestamp() * 1000),
            "end": int(end.timestamp() * 1000),
            "startLocal": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "endLocal": end.strftime("%Y-%m-%dT%H:%M:%S"),
        })
    return seances


def make_event(rng: random.Random, event_id: int, arch: dict) -> tuple[dict, dict]:
    venue_name, venue_kind, lat, lon, street, house = pick_venue(rng, arch["venue_kinds"])
    category = rng.choice(arch["categories"])
    title = rng.choice(arch["titles"])

    price = rng.randrange(*arch["price"]) // 50 * 50
    max_price = price + rng.choice([0, 0, 200, 500, 1000])

    tag_ids = rng.sample(arch["tags"], min(len(arch["tags"]), rng.choice([1, 2, 2, 3])))
    age = rng.choice(arch["age"])

    event = {
        "_id": event_id,
        "name": title,
        "ageRestriction": age,
        "description": f"<p>{arch['blurb']}</p>",
        "shortDescription": arch["blurb"],
        "isPushkinsCard": True,
        "status": "accepted",
        "tags": [
            {"_id": t, "name": TAGS[t][0], "sysName": TAGS[t][1]}
            for t in tag_ids
        ],
        "category": {"name": CATEGORIES[category], "sysName": category},
        "organizer": venue_name,
        "isFree": False,
        "price": price,
        "maxPrice": max_price,
        "saleLink": f"https://example.invalid/synthetic-tickets/{event_id}",
        "image": {
            "name": f"synthetic-{event_id}.jpg",
            "realName": f"synthetic-{event_id}.jpg",
            "author": "—",
            "source": "Синтетические данные",
        },
        "places": [{
            "_id": 900000 + VENUES.index(
                next(v for v in VENUES if v[0] == venue_name)
            ),
            "name": venue_name,
            "locale": KAZAN_LOCALE,
            "category": {"name": venue_kind, "sysName": venue_kind},
            "address": make_address(street, house),
            "mapPosition": {
                "coordinates": [
                    round(lon + rng.uniform(-0.004, 0.004), 6),
                    round(lat + rng.uniform(-0.004, 0.004), 6),
                ],
                "type": "Point",
            },
            "accessible": rng.choice([[], [], ["a3"], ["c1", "c3"], ["e1"]]),
            "isAccessibleCustom": False,
            "saleLink": f"https://example.invalid/synthetic-tickets/{event_id}",
            "seances": make_seances(rng, arch),
        }],
        "_synthetic": True,
    }

    # The answer key. Not part of the API schema; written to a separate file.
    label = {
        "_id": event_id,
        "archetype": arch["key"],
        "true_audience": arch["audience"],
        "name": title,
    }
    return event, label


def main() -> None:
    rng = random.Random(SEED)

    plan: list[dict] = []
    for arch in ARCHETYPES:
        plan += [arch] * round(arch["share"] * TOTAL_EVENTS)
    # Cinema sits in its own budget pool, so give it a fixed slice on top.
    plan += [CINEMA_ARCHETYPE] * round(0.06 * TOTAL_EVENTS)
    rng.shuffle(plan)

    events, labels = [], []
    for i, arch in enumerate(plan, start=1):
        event, label = make_event(rng, 1_600_000 + i, arch)
        events.append(event)
        labels.append(label)

    # The real API sorts by _id descending by default.
    events.sort(key=lambda e: e["_id"], reverse=True)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    envelope = {
        "_synthetic": True,
        "_warning": (
            "СИНТЕТИЧЕСКИЕ ДАННЫЕ. Это НЕ реальная афиша «Пушкинской карты». "
            "Названия площадок — настоящие казанские учреждения, всё остальное "
            "сгенерировано. Ссылки на покупку нерабочие (example.invalid). "
            "Схема повторяет PRO.Культура.РФ API 2.5, чтобы источник можно было "
            "заменить на реальный без изменения кода выше слоя данных."
        ),
        "_schema": "PRO.Культура.РФ API 2.5 — pushkinsCardEvents",
        "_generated_at": generated_at,
        "_seed": SEED,
        "_region": "Республика Татарстан, Казань",
        "events": events,
    }

    OUT.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (OUT.parent / "kazan_events_labels.json").write_text(
        json.dumps(
            {"_synthetic": True, "_generated_at": generated_at, "labels": labels},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    # Report the distribution, so we can sanity-check that the catalogue really
    # does reproduce the problem we claim to solve.
    from collections import Counter

    by_arch = Counter(l["archetype"] for l in labels)
    total_seances = sum(len(e["places"][0]["seances"]) for e in events)
    weekday_daytime = sum(
        1
        for e in events
        for s in e["places"][0]["seances"]
        if datetime.fromisoformat(s["startLocal"]).weekday() < 5
        and datetime.fromisoformat(s["startLocal"]).hour < 16
    )
    kid_events = sum(1 for l in labels if l["true_audience"] in ("babies", "children"))

    print(f"events:   {len(events)}")
    print(f"seances:  {total_seances}")
    print(f"written:  {OUT}")
    print()
    print("by archetype:")
    for key, n in by_arch.most_common():
        print(f"  {key:18s} {n:5d}  ({n / len(events):.0%})")
    print()
    print(f"showtimes on a weekday before 16:00: {weekday_daytime} "
          f"({weekday_daytime / total_seances:.0%} of all showtimes)")
    print(f"events aimed at small children:      {kid_events} "
          f"({kid_events / len(events):.0%} of the catalogue)")


if __name__ == "__main__":
    main()
