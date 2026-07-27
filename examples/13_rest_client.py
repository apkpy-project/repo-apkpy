# ============================================================
#  ApkPy Example 13 — REST Client (full CRUD)
# ============================================================
#  What it shows:
#    • https.get(url, on_response=cb)              -> read
#    • https.post(url, data, ...)                  -> create
#    • https.put(url, data, ...)                   -> replace
#    • https.patch(url, data, ...)                 -> partial update
#    • https.delete(url, on_response=cb)           -> delete
#
#  Every callback receives (success, response):
#    success  -> True for 2xx status codes
#    response -> the response body (JSON string for most APIs)
#
#  This demo talks to jsonplaceholder.typicode.com — a free fake
#  REST API that accepts all five methods. Swap the URLs for your
#  own backend (Supabase, Firebase, Django, FastAPI...).
#
#  Preview : python 13_rest_client.py
#  Android : apkpy build   (INTERNET permission is added automatically)
# ============================================================

from apkpy_lib import Screen, label, button, toast, https, json_get, run

api = Screen(id="api")

label("REST Client 🌐", id="title", screen=api)
label("Full CRUD: GET · POST · PUT · PATCH · DELETE", id="hint", screen=api)

status   = label("Press a button to call the API.", id="status", screen=api)
body_lbl = label("(response will show here)", id="body_lbl", screen=api)

def show_get(ok, resp):
    if ok:
        titulo = json_get(resp, "title")
        status.set_value("GET 200 — read post #1 ✅")
        body_lbl.set_value(f"title: {titulo}")
    else:
        status.set_value("GET failed ❌")
        body_lbl.set_value(resp)

def show_post(ok, resp):
    if ok:
        novo_id = json_get(resp, "id")
        status.set_value("POST 201 — created ✅")
        body_lbl.set_value(f"new id: {novo_id}")
    else:
        status.set_value("POST failed ❌")
        body_lbl.set_value(resp)

def show_put(ok, resp):
    if ok:
        titulo = json_get(resp, "title")
        status.set_value("PUT 200 — replaced ✅")
        body_lbl.set_value(f"title: {titulo}")
    else:
        status.set_value("PUT failed ❌")
        body_lbl.set_value(resp)

def show_patch(ok, resp):
    if ok:
        titulo = json_get(resp, "title")
        status.set_value("PATCH 200 — partial update ✅")
        body_lbl.set_value(f"title: {titulo}")
    else:
        status.set_value("PATCH failed ❌")
        body_lbl.set_value(resp)

def show_delete(ok, resp):
    if ok:
        status.set_value("DELETE 200 — gone ✅")
        body_lbl.set_value("response: {} (deleted)")
    else:
        status.set_value("DELETE failed ❌")
        body_lbl.set_value(resp)

def do_get():
    toast("GET...")
    https.get("https://jsonplaceholder.typicode.com/posts/1", on_response=show_get)

def do_post():
    toast("POST...")
    https.post("https://jsonplaceholder.typicode.com/posts",
               '{"title": "created by ApkPy", "body": "hello", "userId": 1}',
               headers={"Content-Type": "application/json"},
               on_response=show_post)

def do_put():
    toast("PUT...")
    https.put("https://jsonplaceholder.typicode.com/posts/1",
              '{"id": 1, "title": "replaced by ApkPy", "body": "full update", "userId": 1}',
              headers={"Content-Type": "application/json"},
              on_response=show_put)

def do_patch():
    toast("PATCH...")
    https.patch("https://jsonplaceholder.typicode.com/posts/1",
                '{"title": "patched by ApkPy"}',
                headers={"Content-Type": "application/json"},
                on_response=show_patch)

def do_delete():
    toast("DELETE...")
    https.delete("https://jsonplaceholder.typicode.com/posts/1", on_response=show_delete)

button("GET",    id="btn_get",    screen=api, command=do_get)
button("POST",   id="btn_post",   screen=api, command=do_post)
button("PUT",    id="btn_put",    screen=api, command=do_put)
button("PATCH",  id="btn_patch",  screen=api, command=do_patch)
button("DELETE", id="btn_delete", screen=api, command=do_delete)

style = """
api {
    background-color: #0F172A;
}
title {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: bold;
    margin-top: 20px;
}
hint {
    color: #94A3B8;
    font-size: 13px;
}
status {
    color: #38BDF8;
    font-size: 15px;
    margin-top: 12px;
}
body_lbl {
    color: #F59E0B;
    font-size: 12px;
}
btn_get {
    color: #F8FAFC;
    background-color: #10B981;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    margin-top: 12px;
    pressed-color: #047857;
}
btn_post {
    color: #F8FAFC;
    background-color: #6366F1;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #4338CA;
}
btn_put {
    color: #F8FAFC;
    background-color: #F59E0B;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #B45309;
}
btn_patch {
    color: #0F172A;
    background-color: #38BDF8;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #0369A1;
}
btn_delete {
    color: #F8FAFC;
    background-color: #EF4444;
    border-radius: 10px;
    font-weight: bold;
    padding: 12px;
    pressed-color: #B91C1C;
}
"""

if __name__ == "__main__":
    run(start_screen=api)
