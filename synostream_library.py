"""Lightweight card records and viewport calculations, independent of Qt."""


import re


class CardRecord:
    def __init__(self, item, page):
        self.item = item
        match = re.search(r"\b((?:18|19|20|21)\d{2})\b", str(item.get("date") or ""))
        self.year = int(match.group(1)) if match else None
        self.page = page
        self.widget = None

    def release(self):
        if self.widget is not None:
            self.page.recycle_widget(self.widget)
            self.widget = None

    deleteLater = release

    def set_card_size(self, size):
        self.release()

    def refresh_watched_badge(self):
        if self.widget is not None:
            self.widget.refresh_watched_badge()


def visible_range(count, columns, row_height, top, height):
    first_row = max(0, top // row_height - 1)
    last_row = (top + height) // row_height + 2
    return range(min(count, first_row * columns), min(count, last_row * columns))

