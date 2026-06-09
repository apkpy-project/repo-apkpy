# Example 08 — Alert & Confirm Dialogs
# Demonstrates alert() and confirm() — the v0.9.9 APIs for native dialog boxes.
#
# alert(title, message)
#   Shows a simple informational dialog with an OK button.
#   No callback needed — it just informs the user.
#
# confirm(title, message, on_result=callback)
#   Shows a dialog with OK and Cancel buttons. Calls on_result(True) if the
#   user confirms, or on_result(False) if they cancel. Same async pattern as
#   camera.capture / gallery.pick.
#
# Both work identically in the Hot Previewer (native OS dialog) and on a real
# Android device (native AlertDialog) — zero code changes between the two.
#
# Run it with: python 08_alert_and_confirm.py

from apkpy_lib import Screen, label, button, toast, alert, confirm, storage, run

main = Screen(id="main")

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
label("🗨️ Alert & Confirm Demo", id="title", screen=main)
label("Test native dialog boxes — identical code on Preview and Android.", id="subtitle", screen=main)

status = label("No dialog shown yet.", id="status", screen=main)

# ─────────────────────────────────────────────
# ALERT
# ─────────────────────────────────────────────
# alert() is fire-and-forget — no callback, just informs the user.
def mostrar_alerta():
    alert("Atenção", "A sessão vai expirar em 5 minutos.\nGuarda o teu trabalho.")
    status.set_value("Alert shown.")

# ─────────────────────────────────────────────
# CONFIRM — apagar dados
# ─────────────────────────────────────────────
# confirm() is async: on_result(confirmed) is called after the user taps OK or Cancel.
def ao_confirmar_apagar(confirmed):
    if confirmed:
        storage.clear()
        status.set_value("All data cleared.")
        toast("Data cleared!")
    else:
        status.set_value("Cancelled — nothing deleted.")

def apagar_dados():
    confirm(
        "Delete all data?",
        "This will permanently erase all saved data. This action cannot be undone.",
        on_result=ao_confirmar_apagar
    )

# ─────────────────────────────────────────────
# CONFIRM — logout
# ─────────────────────────────────────────────
def ao_confirmar_logout(confirmed):
    if confirmed:
        status.set_value("Logged out.")
        toast("Goodbye!")
    else:
        status.set_value("Logout cancelled.")

def fazer_logout():
    confirm("Log out?", "Are you sure you want to log out?", on_result=ao_confirmar_logout)

button("⚠️ Show Alert",    id="btn_alert",   command=mostrar_alerta, screen=main)
button("🗑️ Delete All Data", id="btn_delete",  command=apagar_dados,  screen=main)
button("🚪 Log Out",        id="btn_logout",  command=fazer_logout,   screen=main)

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
main {
    background-color: #0F172A;
}

title {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: bold;
    margin-top: 28px;
    margin-left: 8px;
}

subtitle {
    color: #94A3B8;
    font-size: 13px;
    margin-top: 4px;
    margin-bottom: 20px;
    margin-left: 8px;
}

status {
    color: #38BDF8;
    font-size: 13px;
    margin-bottom: 12px;
    margin-left: 8px;
}

btn_alert {
    background-color: #1E293B;
    color: #FBBF24;
    border-radius: 12px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 6px;
    pressed-color: #0F172A;
    border-color: #FBBF24;
    border-width: 1px;
}

btn_delete {
    background-color: #1E293B;
    color: #F87171;
    border-radius: 12px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 6px;
    pressed-color: #0F172A;
    border-color: #F87171;
    border-width: 1px;
}

btn_logout {
    background-color: #1E293B;
    color: #94A3B8;
    border-radius: 12px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 6px;
    pressed-color: #0F172A;
    border-color: #475569;
    border-width: 1px;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
