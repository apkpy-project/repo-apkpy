"""People Desk: user-mediated contacts, with a synthetic desktop address book."""
from apkpy_lib import (
    Screen, Theme, app_bar, button, contacts, inputs, json_get, label, run,
    virtual_collection,
)

home = Screen(id="home", scroll=True)
app_bar("People Desk", screen=home)
label("PEOPLE, WITH PERMISSION", id="eyebrow", screen=home)
label("One person. The right details.", id="heading", screen=home)
label("Pick a phone or email without sharing your whole address book. "
      "Browsing asks for Contacts access. Creating and editing use the system editor.", id="intro", screen=home)
status = label("Choose a contact to begin.", id="status", screen=home)

def selected(ok, value):
    if ok:
        contact_id.set_value(json_get(value, "uri"))
        name.set_value(json_get(value, "name"))
        phone.set_value(json_get(value, "phone"))
        email.set_value(json_get(value, "email"))
        status.set_value("Contact selected. Only use these details for the person's requested action.")
    else:
        status.set_value("Contacts: " + value)

def editor_returned(ok, value):
    if ok:
        status.set_value("Editor closed. Changes are not verified: pick the contact again to check.")
    else:
        status.set_value("Contacts: " + value)

def listed(ok, value):
    if ok:
        results.set_items(value)
        status.set_value("First 25 matching contacts. Tap a row to load its details.")
    else:
        status.set_value("Contacts: " + value)

def row_selected(item):
    contacts.get(json_get(item, "uri"), on_result=selected)

def browse():
    status.set_value("Reading contacts…")
    contacts.list(query=search.get_value(), limit=25, on_result=listed)

def settings_returned(ok, value):
    status.set_value("Contacts settings: " + value)

button("Choose phone number", icon="person", screen=home,
       command=lambda: contacts.pick(kind="phone", on_result=selected))
button("Choose email address", variant="outlined", screen=home,
       command=lambda: contacts.pick(kind="email", on_result=selected))
contact_id = inputs("Selected contact reference", id="contact_id", screen=home)
name = inputs("Name for a new contact", id="name", screen=home)
phone = inputs("Phone", id="phone", screen=home)
email = inputs("Email", id="email", screen=home)
button("Create in Contacts", icon="add", screen=home,
       command=lambda: contacts.create(name=name.get_value(), phone=phone.get_value(),
                                       email=email.get_value(), on_result=editor_returned))
button("Edit selected contact", variant="outlined", screen=home,
       command=lambda: contacts.edit(contact_id.get_value(), on_result=editor_returned))
label("BROWSE YOUR ADDRESS BOOK", id="section", screen=home)
search = inputs("Search names", id="search", screen=home)
button("Search · asks for Contacts access", screen=home, command=browse)
button("Permission settings", variant="text", screen=home,
       command=lambda: contacts.settings(on_result=settings_returned))
results = virtual_collection([], template={"title": "{name}", "subtitle": "{phone}", "meta": "{email}"},
                             on_click=row_selected, id="results", screen=home)
label("Desktop entries are fictional and reset when the Previewer restarts. "
      "Nothing is sent to a server. There is no direct delete operation.", id="tip", screen=home)

style = """
home { padding: 20px; background-color: var(--background); }
eyebrow, section { color: var(--primary); font-size: 11px; font-weight: bold; margin-bottom: 12px; }
heading { font-size: 28px; font-weight: bold; color: var(--text); margin-bottom: 12px; }
intro, tip { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; }
status { font-size: 13px; color: var(--primary); margin-bottom: 18px; }
button { min-height: 48px; border-radius: 16px; margin-bottom: 10px; }
contact_id, name, phone, email, search { width: 100%; min-height: 48px; border-radius: 14px; margin-bottom: 10px; }
section { margin-top: 22px; }
results { height: 270px; margin-bottom: 16px; }
"""
run(start_screen=home, theme=Theme(mode="dark"))
