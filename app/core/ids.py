from __future__ import annotations

import itertools
import time

_counter = itertools.count(1)


def new_id() -> str:
    return f"{int(time.time() * 1000)}{next(_counter) % 10000:04d}"

