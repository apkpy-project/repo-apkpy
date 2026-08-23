---
title: Background jobs
description: Persistent work queues that survive backgrounding, network loss, process death and reboots, generated as WorkManager requests.
---

# Background jobs and the offline queue

Some work should not depend on a screen staying open. Uploading a photo,
sending a message written on the underground, flushing a queue of likes,
synchronising local edits: all of it has to survive the user leaving the app,
the network disappearing, Android reclaiming the process and the phone
restarting.

`background_job()` declares that work once. The Previewer runs it against an
on-disk queue; Android runs it as a
[WorkManager](https://developer.android.com/topic/libraries/architecture/workmanager)
`OneTimeWorkRequest`.

```python
from apkpy_lib import background_job, storage

def sync_notes():
    sync_job.progress(20, "Reading local changes")
    folder = sync_job.input("folder_id")
    storage.set("last_synced_folder", folder)
    sync_job.progress(100, "Synchronised")

sync_job = background_job(
    "sync_notes",
    run=sync_notes,
    requires_network=True,
    retry="exponential",
    unique=True,
)
```

Queue work from anywhere in the interface:

```python
sync_job.enqueue({"folder_id": "12"})
```

## Declaring a job

| Argument | Meaning | Android |
| --- | --- | --- |
| `run` | the function executed in the background | the generated `Worker` body |
| `requires_network` | only run with connectivity | `NetworkType.CONNECTED` |
| `requires_unmetered` | only run on an unmetered network | `NetworkType.UNMETERED` |
| `requires_charging` | only run while charging | `setRequiresCharging(true)` |
| `requires_battery_not_low` | skip while the battery is low | `setRequiresBatteryNotLow(true)` |
| `retry` | `"exponential"` or `"linear"` | `BackoffPolicy` |
| `retry_seconds` | first backoff delay, minimum 10 | `setBackoffCriteria` |
| `unique` | one named chain instead of parallel work | `enqueueUniqueWork` |
| `on_conflict` | `"append"`, `"keep"` or `"replace"` | `ExistingWorkPolicy` |

`on_conflict` is what turns a job into a real queue:

- **`"append"`** — every `enqueue` joins the end of the chain and runs in
  order. This is the default and the one an outbox wants.
- **`"keep"`** — a new `enqueue` is ignored while work is already pending. Use
  it for a refresh that must not stack up.
- **`"replace"`** — the pending work is cancelled and replaced by the new
  request.

!!! note "Why append maps to APPEND_OR_REPLACE"
    ApkPy generates `ExistingWorkPolicy.APPEND_OR_REPLACE` for `"append"`.
    Plain `APPEND` cancels newly appended work when the previous item failed
    or was cancelled, which would silently break an offline queue after its
    first failure.

## Inside the job

The `run` function executes off the interface thread — on Android it is a
`Worker` that can run with the app closed. Talk to the interface through
`progress()` and `observe()`, not by calling `set_value()` on components.

```python
def upload_photo():
    upload_job.progress(10, "Preparing")
    path = upload_job.input("path")

    if upload_job.attempt() == "3":
        upload_job.fail()
        return

    if not_ready(path):
        upload_job.retry()
        return

    upload_job.progress(100, "Uploaded")
```

| Call | Meaning |
| --- | --- |
| `job.input(key)` | a value passed to `enqueue({...})` |
| `job.attempt()` | which attempt this is, starting at `"1"` |
| `job.progress(percent, message)` | publish progress to observers |
| `job.retry()` | run again after the backoff |
| `job.fail()` | stop permanently, no further attempts |

`retry()` and `fail()` mark the attempt rather than jumping out, so the result
is identical in both runtimes. Add `return` when you want to stop immediately.

!!! warning "attempt() counts one message, not the queue"
    `attempt` stays at `1` while everything succeeds first time, because it
    counts the tries of a single queued item. It is the same value Android
    exposes as `getRunAttemptCount()`, normalised to start at one.

## Observing progress

```python
def queue_changed(status):
    queue_state.set_value("Queue · " + status["state"])
    queue_detail.set_value(
        "pending " + status["pending"] + " · " + status["progress"] + "%"
    )

sync_job.observe(on_change=queue_changed, screen=home)
```

`on_change` receives one JSON status document in both runtimes:

| Key | Values |
| --- | --- |
| `state` | `idle`, `enqueued`, `running`, `retry`, `success`, `failed`, `cancelled`, and `waiting_network` in the Previewer |
| `progress` | `0` to `100`, as reported by `progress()` |
| `message` | the last message passed to `progress()` |
| `pending` | items waiting to run |
| `running` | items running now |
| `attempt` | attempt number of the current item |

Every value is a string, matching the generated `_jsonGet` accessor, so
`"pending " + status["pending"]` behaves the same on the desktop and on the
phone.

The screen does not poll. On Android the observer is attached to
`getWorkInfosByTagLiveData(...)`, so it survives rotation and is re-delivered
when the Activity resumes — including after the process was killed and the
queue restored.

## Cancelling

```python
sync_job.cancel()
```

Drops everything still queued and abandons the attempt currently running,
exactly like `WorkManager.cancelUniqueWork`.

## Generated Android output

An app that declares one job receives:

- **`ApkpyJobs.java`** — the runtime: one `enqueue_<job>` entry point per
  declared job carrying its constraints, backoff and policy, plus `cancel`
  and the `status` collector that turns a list of `WorkInfo` into the JSON
  document above.
- **`<Job>JobWorker.java`** — the transpiled `run` function, with
  `getInputData()`, `setProgressAsync()` and the attempt result.

WorkManager stores the queue in its own database, so pending work outlives
process death and a reboot without any code in the app. The
`androidx.work:work-runtime` dependency is added to `build.gradle` only when a
worker is actually generated.

Apps that never call `background_job` receive none of it: no runtime class, no
worker and no WorkManager dependency.

## Previewer behaviour

The Previewer implements the same contract on the desktop so the loop stays
fast:

- the queue is stored in `~/.apkpy/jobs` and restored when the script starts
  again, the way WorkManager restores work after a reboot;
- `requires_network` holds the queue while the machine is offline and drains
  it when the connection returns;
- retries use the same backoff policy and the same ten-second floor;
- `unique` and `on_conflict` reproduce the same policies.

Connectivity is decided by checking that the machine has a route *and* that a
well-known host answers on port 443. The route alone is not enough: virtual
adapters from Hyper-V, WSL, VirtualBox or a VPN keep a route alive with the
Wi-Fi switched off.

## Deliberate limits

- The `run` function supports the same background-safe subset as
  `service.every`: `storage`, `db`, `https`, `notify`, and plain logic.
  Component calls need a live Activity and are ignored.
- `https` is **synchronous** inside the generated Worker and **asynchronous**
  in the Previewer. Decide the outcome in the body of the job; calling
  `job.retry()` from an `on_response` callback arrives too late on the
  desktop. See [Previewer versus Android](preview-android.md).
- Periodic work stays with [`service.every`](native-features.md). A job is
  one-shot work you queue; a service is a schedule.
- There is no cross-device sync, no conflict resolution and no server
  component. A job is local work with a persistent queue.

A complete application using all of this is in the
[end-to-end tutorial](tutorial-end-to-end.md), and the release notes for this
feature are in [Version 1.3.2](version-1.3.2.md).
