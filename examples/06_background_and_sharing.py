# Example 06 — Background Services, Notifications, Sharing & Clipboard
# Demonstrates the v0.9.8 APIs: service.every / service.once / service.cancel,
# notify(), share() and clipboard.copy() — all with 100% identical code between
# the Hot Previewer and a real Android device.
# Run it with: python 06_background_and_sharing.py

from apkpy_lib import Screen, label, button, toast, notify, share, clipboard, storage, service, run

main = Screen(id="main")

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
label("⏱️ Background & Sharing Demo", id="title", screen=main)
label("Background sync, notifications, share sheet and clipboard.", id="subtitle", screen=main)

status_label   = label("Background sync: waiting for first run...", id="status",   screen=main)
reminder_label = label("Reminder: not scheduled yet.",               id="reminder", screen=main)

# ─────────────────────────────────────────────
# UI REFRESH
# ─────────────────────────────────────────────
# Background functions can't touch the screen directly — they write to
# `storage`, and the UI reads from it. This keeps the code 100% identical
# between the Previewer and the compiled Android app.
def atualizar_ui():
    status_label.set_value(storage.get("sync_status", "Background sync: waiting for first run..."))
    reminder_label.set_value(storage.get("reminder_status", "Reminder: not scheduled yet."))

# ─────────────────────────────────────────────
# BACKGROUND SERVICE (recurring)
# ─────────────────────────────────────────────
def sincronizar_em_background():
    count = int(storage.get("sync_count", "0")) + 1
    storage.set("sync_count", str(count))
    storage.set("sync_status", f"Background sync #{count} completed")
    notify("Sync complete", f"Background sync #{count} finished successfully.", id="bg_sync")

def parar_sincronizacao():
    service.cancel(id="bg_sync")
    storage.set("sync_status", "Background sync: stopped by the user")
    toast("Background sync cancelled.")
    atualizar_ui()

# ─────────────────────────────────────────────
# ONE-TIME SERVICE (delayed reminder)
# ─────────────────────────────────────────────
def enviar_lembrete():
    storage.set("reminder_status", "Reminder delivered! (service.once already ran)")
    notify("ApkPy Reminder", "Your one-time reminder just arrived!", id="reminder")
    toast("Reminder delivered!")

def agendar_lembrete():
    service.once(run=enviar_lembrete, after_minutes=0.05, id="reminder")
    storage.set("reminder_status", "Reminder scheduled — arriving shortly...")
    toast("Reminder scheduled.")
    atualizar_ui()

# ─────────────────────────────────────────────
# SHARE & CLIPBOARD
# ─────────────────────────────────────────────
def partilhar_resultado():
    count = storage.get("sync_count", "0")
    share(f"My ApkPy app has already run {count} background syncs! 🚀", title="Share result")

def copiar_resultado():
    count = storage.get("sync_count", "0")
    clipboard.copy(f"My ApkPy app has run {count} background syncs!")
    toast("Copied to clipboard!")

button("⏹️ Stop background sync",     id="btn_stop",     command=parar_sincronizacao, screen=main)
button("⏰ Schedule one-time reminder", id="btn_reminder", command=agendar_lembrete,    screen=main)
button("📤 Share result",              id="btn_share",    command=partilhar_resultado, screen=main)
button("📋 Copy result",               id="btn_copy",     command=copiar_resultado,    screen=main)

# ─────────────────────────────────────────────
# SCHEDULE THE RECURRING BACKGROUND SERVICE
# ─────────────────────────────────────────────
# minutes=0.05 (~3s) is only meant for quickly testing the flow in the Previewer.
# On real Android, ApkPy enforces WorkManager's 15-minute minimum automatically.
service.every(run=sincronizar_em_background, minutes=0.05, id="bg_sync",
              only_on_wifi=True, only_when_charging=True)

atualizar_ui()

# ─────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────
style = """
main {
    background-color: #0F172A;
    flex-direction: column;
    padding: 28px;
    gap: 12px;
}

title {
    color: #10B981;
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin-top: 24px;
}

subtitle {
    color: #94A3B8;
    font-size: 13px;
    text-align: center;
    margin-bottom: 18px;
}

status, reminder {
    color: #38BDF8;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 6px;
}

btn_stop {
    background-color: #334155;
    color: #FBBF24;
    border-radius: 14px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    margin-top: 8px;
    pressed-color: #1E293B;
}

btn_reminder {
    background-color: #334155;
    color: #38BDF8;
    border-radius: 14px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    pressed-color: #1E293B;
}

btn_share {
    background-color: #334155;
    color: #34D399;
    border-radius: 14px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    pressed-color: #1E293B;
}

btn_copy {
    background-color: #334155;
    color: #F472B6;
    border-radius: 14px;
    font-weight: bold;
    font-size: 14px;
    padding: 14px;
    pressed-color: #1E293B;
}
"""

if __name__ == "__main__":
    run(start_screen=main)
