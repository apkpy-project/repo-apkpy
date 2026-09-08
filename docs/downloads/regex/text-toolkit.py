"""Text Toolkit: validate input, extract tags/references, and clean whitespace."""
import re
from apkpy_lib import Screen, Theme, app_bar, label, inputs, button, list_view, run

home = Screen(id="home", scroll=True)
app_bar("Text Toolkit", screen=home)
label("Check, extract, clean.", variant="title", screen=home)
label("Local text tools powered by Python re and native Android regex.", screen=home)
email = inputs("Email address", type="text", screen=home)
message = inputs("Message, tags and references", type="textarea", screen=home)
status = label("Enter text, then run the checks.", screen=home)
reference = label("Reference: none", screen=home)
cleaned = label("Clean text: —", screen=home)
tags = list_view([], screen=home)


def check_text():
    value = email.get_value()
    text = message.get_value()
    # Format check, not proof that an address exists or owns an inbox.
    if re.match(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\Z", value):
        status.set_value("Email format: valid")
    else:
        status.set_value("Check the email format")
    found = re.search(r"\bREF-(?P<code>[0-9]{4,8})\b", text, re.I)
    if found is not None:
        reference.set_value("Reference: " + found.group("code"))
    else:
        reference.set_value("Reference: none")
    cleaned.set_value(re.sub(r"\s+", " ", text).strip())
    results = re.findall(r"#[\w]+", text)
    tags.set_items(results)


button("Check text", command=check_text, screen=home)
run(start_screen=home, theme=Theme(mode="dark"))
