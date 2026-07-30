"""Two-column catalog with incremental pages and server reconciliation."""

from apkpy_lib import (
    Screen, Theme, app_bar, button, container, device, label, run, toast,
    virtual_collection,
)


PRODUCTS = [
    {"sku": "lamp-01", "image": "https://picsum.photos/seed/catalog-lamp/420/320",
     "name": "Arc lamp", "detail": "Warm aluminium light", "price": "$129",
     "stock": "IN STOCK"},
    {"sku": "chair-02", "image": "https://picsum.photos/seed/catalog-chair/420/320",
     "name": "Low chair", "detail": "Wool and oak", "price": "$240",
     "stock": "4 LEFT"},
    {"sku": "desk-03", "image": "https://picsum.photos/seed/catalog-desk/420/320",
     "name": "Field desk", "detail": "Compact work surface", "price": "$310",
     "stock": "IN STOCK"},
    {"sku": "shelf-04", "image": "https://picsum.photos/seed/catalog-shelf/420/320",
     "name": "Line shelf", "detail": "Powder-coated steel", "price": "$175",
     "stock": "NEW"},
]

MORE_PRODUCTS = [
    {"sku": "clock-05", "image": "https://picsum.photos/seed/catalog-clock/420/320",
     "name": "Studio clock", "detail": "Silent movement", "price": "$84",
     "stock": "IN STOCK"},
    {"sku": "tray-06", "image": "https://picsum.photos/seed/catalog-tray/420/320",
     "name": "Stone tray", "detail": "Hand-finished surface", "price": "$58",
     "stock": "2 LEFT"},
]

catalog_screen = Screen(id="catalog_screen", scroll=True)
app_bar("Object Index", screen=catalog_screen)


def open_product(item):
    toast(item["name"] + " - " + item["price"])


def next_page():
    catalog.append_items(MORE_PRODUCTS, has_more=False)
    status.set_value("Six products - end of catalog")


def sync_prices():
    catalog.merge_items(
        [
            {"sku": "lamp-01", "price": "$119", "stock": "PRICE DROP"},
            {"sku": "vase-07",
             "image": "https://picsum.photos/seed/catalog-vase/420/320",
             "name": "Glass vase", "detail": "Smoke finish", "price": "$72",
             "stock": "REMOTE"},
        ],
        key="sku",
    )
    status.set_value("Lamp updated; Glass vase appended")
    toast("Catalog reconciled by SKU")


def hide_chair():
    catalog.remove_item("chair-02", key="sku", optimistic="hide-chair")
    status.set_value("Low chair hidden - RESTORE can roll it back")


def restore_chair():
    catalog.rollback("hide-chair")
    status.set_value("Low chair restored")


label("VIRTUAL GRID", id="kicker", screen=catalog_screen)
label("A catalog without full reloads.", id="title", screen=catalog_screen)
status = label("Four products loaded", id="status", screen=catalog_screen)

catalog = virtual_collection(
    PRODUCTS,
    template={
        "image": "{image}", "title": "{name}", "subtitle": "{detail}",
        "meta": "{price}", "badge": "{stock}",
    },
    id="catalog",
    layout="grid",
    columns=2,
    item_height=238,
    buffer=2,
    on_click=open_product,
    on_end_reached=next_page,
    prefetch=2,
    screen=catalog_screen,
)

sync_row = container(id="sync_row", screen=catalog_screen)
button("SYNC PRICES", command=sync_prices, parent=sync_row)
button("HIDE CHAIR", variant="outlined", command=hide_chair, parent=sync_row)
button("RESTORE", variant="text", command=restore_chair, screen=catalog_screen)

theme = Theme(
    mode="dark", primary="#F97352", secondary="#61D8A6",
    background="#0D0E10", surface="#181A1E", text="#F7F4EF",
    text_secondary="#A6A29B", border="#32343A", radius=16, spacing=14,
)

style = """
catalog_screen { background-color: var(--background); padding: 18px; }
kicker { color: var(--secondary); font-size: 11px; font-weight: bold; }
title { color: var(--text); font-size: 25px; font-weight: bold; }
status { color: var(--secondary); font-size: 12px; margin-bottom: 8px; }
catalog {
    height: 590px; item-background-color: var(--surface);
    item-border-color: var(--border); title-color: var(--text);
    subtitle-color: var(--text-secondary); meta-color: var(--secondary);
    badge-background-color: var(--primary); badge-color: #111111;
}
sync_row { display: flex; flex-direction: row; gap: 10px; margin-top: 12px; }
button { flex-grow: 1; border-radius: 15px; min-height: 46px; }
"""

device("Pixel 9")
run(start_screen=catalog_screen, theme=theme)
