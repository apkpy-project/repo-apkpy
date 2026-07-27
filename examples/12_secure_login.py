# ============================================================
#  ApkPy Example 12 — Secure Login (password hashing + salting)
# ============================================================
#  What it shows:
#    • crypto.hash_password(pw)        -> "pbkdf2-sha256$200000$<salt>$<hash>"
#    • crypto.verify_password(pw, h)   -> True / False
#    • Storing ONLY the hash in storage (never the plain password)
#
#  Why it matters: anyone can decompile an APK. If you store the
#  password as plain text in SharedPreferences, it's exposed. With
#  hash + random salt, the stored value reveals nothing — and you
#  don't need to import hashlib: crypto is built into ApkPy.
#
#  Preview : python 12_secure_login.py
#  Android : apkpy build
# ============================================================

from apkpy_lib import Screen, label, inputs, button, toast, storage, crypto, run

login = Screen(id="login")

label("Secure Login 🔒", id="title", screen=login)
label("Password is stored as hash+salt — never plain text.", id="hint", screen=login)

pw_in  = inputs("Password", id="pw_in", type="password", screen=login)
status = label("No account yet — register first.", id="status", screen=login)

def register():
    senha = pw_in.get_value()
    # Stores "pbkdf2-sha256$200000$<salt>$<hash>" — PBKDF2 key stretching
    # makes GPU brute-force ~200,000x slower; decompiling reveals nothing.
    storage.set("pw_hash", crypto.hash_password(senha))
    status.set_value("Account created. Now try LOGIN.")
    toast("Registered! 🔒")

def do_login():
    senha    = pw_in.get_value()
    guardado = storage.get("pw_hash", "")
    ok = crypto.verify_password(senha, guardado)
    if ok:
        status.set_value("Welcome back! ✅")
        toast("Login OK!")
    else:
        status.set_value("Wrong password. ❌")
        toast("Wrong password.")

button("REGISTER", id="btn_reg", screen=login, command=register)
button("LOGIN",    id="btn_log", screen=login, command=do_login)

style = """
login {
    background-color: #0F172A;
}
title {
    color: #F8FAFC;
    font-size: 24px;
    font-weight: bold;
    margin-top: 24px;
}
hint {
    color: #94A3B8;
    font-size: 13px;
}
pw_in {
    color: #F8FAFC;
    background-color: #1E293B;
    border-radius: 10px;
    padding: 12px;
    margin-top: 16px;
}
status {
    color: #38BDF8;
    font-size: 15px;
    margin-top: 12px;
}
btn_reg {
    color: #F8FAFC;
    background-color: #6366F1;
    border-radius: 10px;
    font-weight: bold;
    padding: 14px;
    margin-top: 16px;
    pressed-color: #4338CA;
}
btn_log {
    color: #F8FAFC;
    background-color: #10B981;
    border-radius: 10px;
    font-weight: bold;
    padding: 14px;
    pressed-color: #047857;
}
"""

if __name__ == "__main__":
    run(start_screen=login)
