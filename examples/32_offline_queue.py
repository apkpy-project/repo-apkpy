"""An offline queue: a background job that saves what it fetched.

The job downloads a page, saves it in the database from inside the download's
on_result, and tidies up; the screen counts the saved pages through an
observer. Inside a job the data layer and files.download() answer before the
next line -- on the phone, where the job is a WorkManager Worker, and in the
Previewer. It also calls your own functions and checks a permission.

A job has no screen. Add this line to work() and run it again:

    status.set_value("from the job")

The Previewer stops the job with J7004, and `apkpy build` refuses it with the
same code and the line number.

Needs ApkPy 1.11.0.
"""

from apkpy_lib import *

PAGE = "https://example.com/"

style = """
body { background-color: #0f1115; }
#title { color: #f3f4f6; font-size: 22px; font-weight: bold; margin-top: 24px; }
#hint { color: #9ca3af; font-size: 14px; margin-top: 6px; }
#status { color: #e5e7eb; font-size: 16px; margin-top: 24px; }
#pages { color: #e5e7eb; font-size: 16px; margin-top: 6px; }
#step { color: #a5b4fc; font-size: 14px; margin-top: 6px; }
#go { background-color: #4f46e5; color: #ffffff; border-radius: 12px;
      font-size: 16px; margin-top: 28px; margin-left: 18px; margin-right: 18px; }
"""

page = db.model("page", fields={
    "id": db.integer(primary_key=True, auto_increment=True),
    "path": db.text(),
})
schema = db.schema("job_bodies_lab", version=1, models=[page])

home = Screen(id="home")
label("Job bodies", id="title", screen=home)
label("A job that downloads a page, saves it and tidies up.",
      id="hint", screen=home)
status = label("Idle", id="status", screen=home)
pages = label("Saved pages: 0", id="pages", screen=home)
step = label("", id="step", screen=home)


def remember(what):
    storage.set("last_step", what)


def saved(new_id):
    remember("saved page #" + str(new_id))


def downloaded(ok, path):
    if ok:
        page.insert({"path": path}, on_result=saved)
    else:
        remember("download failed")


def tidy():
    files.delete("old.txt")


def work():
    if permissions.has("CAMERA"):
        remember("camera allowed")
    else:
        remember("no camera")
    files.download(PAGE, "page.html", on_result=downloaded)
    tidy()
    job.progress(100, "done")


job = background_job("fetch_page", run=work, requires_network=True)


def show(doc):
    status.set_value("Job: " + doc["state"] + " " + doc["message"])
    step.set_value("Last step: " + storage.get("last_step"))


def count(rows):
    pages.set_value("Saved pages: " + str(len(rows)))


job.observe(on_change=show, screen=home)
saved_pages = page.observe(on_change=count, screen=home)
button("Run the job", id="go", screen=home, command=lambda: job.enqueue())
service.every(tidy, 15, "tidy_service")
run(start_screen=home)
