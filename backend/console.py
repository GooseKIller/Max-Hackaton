"""
Run the bot in a terminal. No MAX token needed.

The dialog is transport-agnostic, so this is the same conversation a MAX user will
have — which makes it the fastest way to iterate on wording and on the filters
before we have a bot token.

    python3 backend/console.py

Type 'выход' to quit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.catalog import build_source  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Store  # noqa: E402
from app.dialog import Dialog  # noqa: E402

BOLD = "\033[1m"
DIM = "\033[2m"
OFF = "\033[0m"


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    path = root / settings.catalog_path
    if not path.exists():
        print(f"No catalogue at {path}")
        print("Generate it first:  python3 data/generate_fixtures.py")
        raise SystemExit(1)

    source = build_source(
        api_key=settings.proculture_api_key,
        subordinations=settings.proculture_subordinations or None,
        fixture_path=path,
    )
    store = Store(root / settings.db_path)
    dialog = Dialog(source, store)
    print(f"{DIM}Каталог: {len(source.all_events())} событий, "
          f"{'тестовые данные' if source.is_synthetic else 'реальные данные'}, "
          f"как от {source.as_of}{OFF}")
    st = store.stats()
    print(f"{DIM}БД: {st['path']} · {st['users']} польз., "
          f"{st['interactions']} сигналов{OFF}\n")

    # Resume rather than reset, so persistence is visible across runs.
    # Type "заново" to start over.
    known = store.load_profile("console") is not None
    render(dialog.handle("console", "продолжить" if known else "/start"))
    if known:
        top = store.top_features("console", n=5)
        if top:
            print(f"{DIM}Вкус из прошлых сессий: "
                  + ", ".join(f"{f}={w:+.1f}" for f, w in top) + f"{OFF}\n")

    while True:
        try:
            text = input(f"{BOLD}> {OFF}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in ("выход", "exit", "quit", ":q"):
            return
        render(dialog.handle("console", text))


def render(reply) -> None:
    print()
    print(reply.text)
    if getattr(reply, "image_url", None):
        print(f"{DIM}[фото] {reply.image_url[:78]}{OFF}")
    if reply.buttons:
        print(f"{DIM}[ " + " ]  [ ".join(reply.buttons) + f" ]{OFF}")
    print()


if __name__ == "__main__":
    main()
