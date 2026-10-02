"""Sign up - a form that says what is wrong with it.

Five text fields. Two are required, three carry help text under them, and
one opens with an error already showing. The button checks the required
fields with validate() -- every empty one turns red at once, each with its
own words -- and then applies two rules of its own with set_error(): an
address needs an @, a password eight characters. Typing in a field clears
its error.

Needs ApkPy 1.12.0.
"""

from apkpy_lib import *

home = Screen("home")

label("Create account", id="title", screen=home)

name = inputs("Full name", id="name", required=True, screen=home)
email = inputs("Email", id="email", help="We only use it to sign you in",
               required="Enter your email", screen=home)
password = inputs("Password", id="password", type="password",
                  help="At least 8 characters", screen=home)
code = inputs("Invite code", id="code", error="That code has expired", screen=home)
about = inputs("About you", id="about", type="textarea",
               help="Optional. Shown on your profile.", screen=home)
said = label("", id="said", screen=home)


def send():
    if not validate(name, email):
        said.set_value("Fix the fields in red")
        return
    if "@" not in email.get_value():
        email.set_error("That does not look like an email address")
        return
    if len(password.get_value()) < 8:
        password.set_error("Use 8 characters or more")
        return
    code.set_error("")
    said.set_value("Welcome, " + name.get_value())


button("Create account", id="go", command=send, screen=home)

style = """
title { font-size: 24px; font-weight: bold; margin-bottom: 8px; }
email, password { border-width: 1px; border-color: #79747E; border-radius: 8px; }
code, about { background-color: #ECE6F0; border-radius: 12px; }
go { margin-top: 12px; }
"""

run(home, theme=Theme())
