---
title: Contacts
description: A scoped contact picker, paginated address-book reads and user-mediated Android contact editors.
---

# Contacts

Choose one phone number or email, look up contacts with permission, or open
the system editor to let the person create or edit a contact. Useful for CRM
clients, appointment apps and user-selected recipients. ApkPy does not upload
the address book or send messages on your behalf.

## Smallest complete example

```python
from apkpy_lib import Screen, button, contacts, json_get, label, run

home = Screen(id="home")
details = label("Choose a phone number", screen=home)

def picked(ok, value):
    if ok:
        details.set_value(json_get(value, "name") + ": " + json_get(value, "phone"))
    else:
        details.set_value("Contacts: " + value)

button("Choose phone", screen=home,
       command=lambda: contacts.pick(kind="phone", on_result=picked))
run(start_screen=home)
```

This app declares neither `READ_CONTACTS` nor `WRITE_CONTACTS`. Android opens
its contact picker and delegates access to the chosen phone/email row, not
the whole address book. A contact with several numbers may require another
choice in the system UI. Use `kind="email"` to select an email instead.

## API and callback contract

All `on_result` callbacks receive `(ok, value)` on the UI thread. On failure,
`value` is a reason string; on success it depends on the operation below.

| Method | Successful result |
| --- | --- |
| `contacts.pick(kind="phone", on_result=None)` | One contact JSON object containing the chosen phone or email |
| `contacts.list(query="", limit=50, offset=0, on_result=None)` | JSON array of contacts; empty array is a successful empty result |
| `contacts.get(id, on_result=None)` | One contact JSON object; accepts a numeric id or returned lookup `uri` |
| `contacts.create(name="", phone="", email="", on_result=None)` | Editor-return JSON; **not proof that the contact was saved** |
| `contacts.edit(id, on_result=None)` | Editor-return JSON; the native app owns save/cancel |
| `contacts.settings(on_result=None)` | `"opened"` after opening the app's Android settings |

Those signatures are what they say: every argument can be given by name or 
by position, and `on_result` is the last one, so `contacts.pick("phone", picked)`
is the same call. Naming it is still clearer, and it is what the examples do.

Row shape:

```json
{"id":"42","uri":"content://com.android.contacts/contacts/lookup/key/42","name":"Alex","phone":"+1 202-555-0101","email":"","phones":["+1 202-555-0101"],"emails":[]}
```

All seven fields exist. `phones` and `emails` contain unique non-empty strings.
The singular fields contain the first entry. The picker returns **only the
selected detail**: choosing a phone leaves `email` empty and `emails` empty,
even if that person has email data. It does not perform a hidden full-contact
read. `list` and `get` return phone/email details available to the provider.

Use `json_get()` for fields and pass the successful `list` result directly to
`virtual_collection.set_items()`. Prefer the lookup URI to a numeric id when
storing a selection; contacts can be merged or removed by other applications.
Neither form is a permanent identity credential.

## Browse with explicit permission

The following snippets extend an app with `search` input, `status` label and
`people` virtual collection. For all declarations together, use
[People Desk](../downloads/contacts/people-desk.py).

```python
def loaded(ok, value):
    if ok:
        people.set_items(value)
    else:
        status.set_value("Contacts: " + value)

def search_people():
    contacts.list(query=search.get_value(), limit=25, offset=0, on_result=loaded)
```

`list` and `get` add `READ_CONTACTS` to the manifest and ask at the time of use.
No permission is requested just because the app starts. Refusal reports
`permission_denied`; if Android will no longer show the prompt it reports
`permission_blocked`. Open `contacts.settings()` only after explaining why
access is needed, then let the person decide. Managed-device policies and
Android's permission history can also prevent prompting.

Search is a literal substring of the display name, using SQLite's ASCII
case-insensitive behavior; it is not a phone/email search or full Unicode
case folding. `%` and `_` are literal characters, not SQL wildcards.
Results sort by display name (`NOCASE`), then id. `limit` is 1–100 and `offset`
is 0–100000. Changes made between pages can shift offsets; refresh after edits.

Queries run on a dedicated background executor. Each non-empty page uses a
base contact query and one batched phone/email query, not one query per row.
Pagination skips through a provider cursor; very large offsets are not a
constant-time database cursor API. No photos, notes, groups or accounts are read.

To request a later page, pass a larger `offset` and append the result instead
of replacing the collection. Here is the callback for a second 25-item page:

```python
def next_page_loaded(ok, value):
    if ok:
        people.append_items(value, has_more=False)
    else:
        people.finish_load(has_more=True)
        status.set_value("Contacts: " + value)

def load_second_page():
    contacts.list(query=search.get_value(), limit=25, offset=25,
                  on_result=next_page_loaded)
```

This example deliberately stops after two pages. In a longer directory, keep
the offset and end-of-results policy in your app; no total count or next-page
cursor is returned. Reset the offset when changing the search query.

## Create and edit with the system UI

```python
def editor_closed(ok, value):
    if ok:
        status.set_value("Editor closed. Pick the contact again to verify changes.")
    else:
        status.set_value("Contacts: " + value)

def new_customer():
    contacts.create(name="Example customer", phone="+1 202-555-0101",
                    email="customer@example.com", on_result=editor_closed)
```

Creation passes these fields to Android's `ACTION_INSERT` editor. Editing
opens `ACTION_EDIT` for the chosen contact. **There is no `WRITE_CONTACTS`
permission and no direct insert/update/delete of the provider.** The person
selects the account and chooses whether to save; a synchronized account may
sync changes according to that account's settings.

After either editor returns, success contains:

```json
{"status":"editor_returned","result_code":"ok","uri":""}
```

`result_code` is `"ok"` or `"cancelled"`, reflecting Android's activity result.
Some OEM editors save without returning an URI or return `cancelled` even
after a change. Therefore `ok=True` means only **the editor returned**, not
that a write was confirmed. Do not announce "Saved" based on this callback.
Pick or reload the contact to verify. An edit of a stale URI is handled by the
native editor, which may show its own error.

```python
def edit_selected():
    contacts.edit(contact_reference.get_value(), on_result=editor_closed)

def reload_selected():
    contacts.get(contact_reference.get_value(), on_result=picked)
```

Here `contact_reference` is an input containing the selected row's `uri`, and
`picked` is the result handler shown above. Reloading calls `get` and therefore
requires read permission; choosing again with `pick` does not.

## Failures and lifecycle

| Reason | Action |
| --- | --- |
| `cancelled` | No picker selection; leave the existing value unchanged |
| `permission_denied` | Explain the read-only use case; offer the scoped picker |
| `permission_blocked` | Offer app settings, without looping permission prompts |
| `not_found` | Refresh a stale selection |
| `unsupported` | No compatible picker/editor/settings activity exists |
| `busy` | Finish the current contacts operation first |
| `invalid` | Check kind, contact reference or page bounds |
| `unavailable` | Use an active foreground screen, not a background job |
| `unknown` | Inspect the technical log; do not log address-book contents |

One operation may be active per screen. Results wait while the Activity is
paused and return on resume. Pending picker/editor/permission operations and
callback names are saved for Activity recreation. An interrupted read can be
reissued after recreation. Destroyed instances cancel queries and discard old
callbacks. Background-job calls are rejected at compile time.

## Previewer

The themed panel says **CONTACTS · SIMULATED**. It contains only fictional
entries; it never reads or writes your computer's contacts. Pick a row, search,
simulate allowing/denying/blocking read access, or save/cancel an in-frame form.
Simulated edits persist for the Previewer process and reset on restart.
Changing screen closes a simulated panel. The desktop UI tests application
flow, not Android's provider, delegated grants, account sync or OEM editors.

Full lab: [download People Desk](../downloads/contacts/people-desk.py), also
available as `examples/30_contacts.py` in the repository. The library workspace
copy is `playground/contacts_lab/writehere.py`.

## Limits and privacy

No bulk writes, direct deletion, contact observers, cloud synchronization,
groups, photos, vCards, call/SMS sending or default-dialer behavior is included.
For one recipient, use the picker rather than reading the whole address book.
Do not collect or upload contacts merely because the user granted permission.
Apps not using `contacts` receive no contacts helper; picker/editor-only apps
receive no address-book permission or new Android dependency.

## Validation status

People Desk reached a real Gradle build and a Python-free APK inspection.
The connected-phone check opened and cancelled the native phone picker.
No real address-book listing, saving/editing or rotation flow was verified in
that check. The simulator cannot certify provider grants or OEM editor results.
See [1.9.0 verification](../version-1.9.0.md#contacts) for the test counts and
remaining checks; this guide is not a publication announcement.

Related: [NFC tags](nfc.md), [1.9.0 scope](../version-1.9.0.md),
[device API](../reference/device.md#contacts-190) and
[troubleshooting](../troubleshooting.md#contacts-190).

Platform references: [contact intents](https://developer.android.com/guide/components/intents-common#Contacts),
[reading contacts](https://developer.android.com/identity/providers/contacts-provider/retrieve-names),
[editing through intents](https://developer.android.com/identity/providers/contacts-provider/modify-data).
