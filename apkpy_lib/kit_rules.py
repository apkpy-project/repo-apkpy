# -*- coding: utf-8 -*-
"""The calls that reach the rest of the phone -- said once, for both runtimes.

    haptics.tap()                                   speech.say("Welcome back")
    browser.open("https://example.com")             phone.dial("912 345 678")
    files.save_as("notes.txt", text, on_result=saved)
    downloads.start(url, on_result=landed)          recorder.start()
    calendar.add_event("Dentist", "2026-11-03 15:30")
    printing.html(invoice, name="Invoice 42")       incoming.links("notes")

None of these is a component and none of them belongs to one screen: they ask
the phone, or another app on it, to do something. On the phone each is a few
lines of Java in a class of its own; on the desk the Previewer stands in with
something a person can see and answer. Both read this table: which calls
exist, what each takes and in which order, what a call answers and with which
words. A word the phone can answer and the desk has never heard of is how the
two drift apart, so the words are written here and nowhere else.

Four shapes of call:

* **do** -- it happens now and answers one word, ``"ok"`` or why not.
* **value** / **flag** -- it answers a text, or yes/no.
* **later** -- the answer needs a person or takes time, and arrives in
  ``on_result(ok, value)``: ``value`` is the result when ``ok`` and one of the
  words when not.
* **declare** -- written once at the top of the file; it changes what is
  built (the manifest), not what runs.

Everything an app passes crosses as text, like every value in an ApkPy app,
and :func:`number`, :func:`whole`, :func:`truth` and :func:`when` say what the
text is read as. ApkpyKit and ApkpyHandoff are these functions again in Java;
a test compiles them and asks both the same questions.

Nothing here imports Tk or anything Android.
"""
from __future__ import annotations

import datetime as _datetime
import re

from . import native_rules

__all__ = [
    "CODE", "DOCS", "DO", "VALUE", "FLAG", "LATER", "DECLARE", "REQUIRED",
    "SPEC", "Verb", "namespaces", "verb", "verbs", "reasons", "signature",
    "label", "trim", "number", "whole", "truth", "flag", "clamp", "when",
    "event_times", "web_address", "link_scheme", "phone_number", "WEB",
    "SHARE_KINDS", "FEEDBACK", "LIMITS", "RESERVED_SCHEMES",
    "speaking_seconds", "refuse", "HEALTH_KINDS", "health_kinds",
    "health_value", "ADS_TEST", "ad_app_id", "ad_unit", "AD_POSITIONS",
    "UPDATE_MODES", "GRADLE", "DECLARED_BY", "health_period", "health_sample",
    "HEALTH_AVERAGES", "AD_REWARD", "file_name", "TIMER_SHORTEST",
    "TIMER_LONGEST", "timer_millis", "timer_next", "timer_not_a_function",
    "timer_called", "timer_swapped", "timer_takes_nothing", "timer_at_the_top",
    "NETWORK_KINDS", "network_kind", "network_online", "network_metered",
    "network_state", "ORIENTATIONS", "LARGE_SCREEN", "BRIGHTNESS_AUTO", "BRIGHTNESS_OWN",
    "BRIGHTNESS_INVALID", "display_orientation", "display_brightness",
    "display_at_the_top", "display_wrong_orientation", "display_wrong_brightness",
    "DOCS_OF", "APP_LOCK_INVALID", "APP_LOCK_FILE", "APP_LOCK_WORDS", "app_lock_minutes",
    "app_lock_due", "app_lock_title", "app_lock_heading", "app_lock_at_the_top", "app_lock_wrong_minutes",
]

CODE = "U2048"
DOCS = "https://repo-apkpy.pages.dev/guides/phone-actions/"
# The families an app has outside its own screens have a page of their own.
DOCS_OUTSIDE = "https://repo-apkpy.pages.dev/guides/outside-the-app/"
OUTSIDE = ("home_widget", "quick_tile", "ads", "updates", "health")


# And so do these three.
DOCS_OF = {
    "timer": "https://repo-apkpy.pages.dev/guides/timers/",
    "network": "https://repo-apkpy.pages.dev/guides/network/",
    "display": "https://repo-apkpy.pages.dev/guides/display/",
    "app_lock": "https://repo-apkpy.pages.dev/guides/app-lock/",
}


def docs_for(message):
    """The page that explains the family a message is about."""
    family = re.match(r"[a-z_]+", str(message))
    name = family.group(0) if family else ""
    return DOCS_OUTSIDE if name in OUTSIDE else DOCS_OF.get(name, DOCS)

DO, VALUE, FLAG, LATER, DECLARE = "do", "value", "flag", "later", "declare"


class _Required:
    def __repr__(self):
        return "REQUIRED"


REQUIRED = _Required()


class Verb:
    """One call: its shape, its arguments in order, and where it lands."""

    def __init__(self, mode, params=(), java="", fixed=(), needs=(), says="", home=""):
        self.mode = mode
        self.params = tuple(params)       # (name, kind, default)
        self.java = java                  # the static method that does it
        self.fixed = tuple(fixed)         # constants handed over before the arguments
        self.needs = tuple(needs)         # keys of NEEDS
        self.says = says                  # one line, for the reference and the errors
        self.home = home                  # its class, when not the family's own

    @property
    def names(self):
        return tuple(name for name, _kind, _default in self.params)

    @property
    def required(self):
        return tuple(name for name, _kind, default in self.params if default is REQUIRED)


def _p(name, kind="text", default=REQUIRED):
    return (name, kind, default)


# ── the calls ────────────────────────────────────────────────────────────────
#
# namespace -> {"class": the Java class, "says": one line, "reasons": {word:
# what it means to the person holding the phone}, "verbs": {name: Verb}}.
SPEC = {
    "haptics": {
        "class": "ApkpyHaptics",
        "says": "A touch you can feel, and the vibration motor.",
        "reasons": {
            "ok": "The phone was asked to do it.",
            "off": "The owner has that kind of vibration switched off, so the phone stays still.",
            "no_vibrator": "This device has no vibration motor.",
        },
        "verbs": {
            "tap": Verb(DO, java="feedback", fixed=("tap",),
                        says="The light click of pressing something."),
            "tick": Verb(DO, java="feedback", fixed=("tick",),
                         says="Lighter still: a value changing under the finger."),
            "heavy": Verb(DO, java="feedback", fixed=("heavy",),
                          says="The firm bump of a long press."),
            "success": Verb(DO, java="feedback", fixed=("success",),
                            says="It worked."),
            "error": Verb(DO, java="feedback", fixed=("error",),
                          says="It did not."),
            "vibrate": Verb(DO, [_p("ms", "whole", 200)], java="vibrate",
                            needs=("vibrate",),
                            says="The app's own buzz: run the motor for this many milliseconds."),
            "available": Verb(FLAG, java="available",
                              says="Whether there is a motor at all."),
        },
    },
    "speech": {
        "class": "ApkpySpeech",
        "says": "The phone reading text aloud, and writing down what it hears.",
        "reasons": {
            "ok": "It was said to the end.",
            "stopped": "Something else was said, or stop() was called, before the end.",
            "no_engine": "No text-to-speech engine is installed or it would not start.",
            "language_unavailable": "The engine has no voice for that language.",
            "failed": "The engine gave up on this text.",
            "cancelled": "The person closed the microphone without speaking.",
            "nothing_heard": "The microphone opened and no words were recognised.",
            "no_recogniser": "No app on this phone turns speech into text.",
        },
        "verbs": {
            "say": Verb(LATER, [_p("text"), _p("language", "text", ""),
                                _p("rate", "number", 1.0), _p("pitch", "number", 1.0)],
                        java="say", needs=("tts",),
                        says="Read this aloud; on_result when it has been said."),
            "stop": Verb(DO, java="stop", says="Stop reading."),
            "is_speaking": Verb(FLAG, java="isSpeaking",
                                says="Whether something is being read right now."),
            "listen": Verb(LATER, [_p("prompt", "text", ""), _p("language", "text", "")],
                           java="listen", needs=("launcher", "recognise"),
                           says="Open the microphone; on_result gets the words."),
            "can_listen": Verb(FLAG, java="canListen", needs=("recognise",),
                               says="Whether this phone can turn speech into text."),
        },
    },
    "browser": {
        "class": "ApkpyBrowser",
        "says": "A web page: over the app in the phone's browser, or inside the app.",
        "reasons": {
            "ok": "The page was opened (open), or was closed by the person (show).",
            "invalid": "The address is not an http:// or https:// one, and there was no html=.",
            "no_browser": "No app on this phone opens web pages.",
        },
        "verbs": {
            "open": Verb(DO, [_p("url")], java="open",
                         says="The page in a browser tab drawn over the app."),
            "show": Verb(LATER, [_p("url", "text", ""), _p("html", "text", ""),
                                 _p("title", "text", "")],
                         java="show", needs=("internet",),
                         says="The page, or your own HTML, inside the app."),
        },
    },
    "files": {
        "class": "ApkpySaveFile",
        "says": "The app's own text files, and a file handed to the person.",
        "reasons": {
            "ok": "The file was written.",
            "invalid": "That is not the name of a file in the app's folder.",
            "cancelled": "The person closed the picker without choosing a place.",
            "not_found": "There is no such file in the app to copy out.",
            "no_app": "This phone has no file picker.",
            "failed": "The file could not be written: the place refused it, or no room is left.",
        },
        "verbs": {
            # Kept in the app's own folder, so there is nobody to ask: these
            # three have a class of their own, without the screen that waits.
            "read": Verb(VALUE, [_p("name")], java="read", home="ApkpyFiles",
                         says="The text of one of the app's files (\"\" when there is none)."),
            "write": Verb(DO, [_p("name"), _p("text")], java="write", home="ApkpyFiles",
                          says="Keep this text as one of the app's files, "
                               "in place of what was there."),
            "append": Verb(DO, [_p("name"), _p("text")], java="append", home="ApkpyFiles",
                           says="Add this text to the end of one of the app's files."),
            "save_as": Verb(LATER, [_p("name"), _p("text"), _p("mime", "text", "text/plain")],
                            java="saveText", needs=("launcher",),
                            says="Ask where, and write this text there."),
            "save_copy": Verb(LATER, [_p("path"), _p("name", "text", "")],
                              java="saveCopy", needs=("launcher",),
                              says="Ask where, and copy one of the app's files there."),
        },
    },
    "downloads": {
        "class": "ApkpyDownloads",
        "says": "A download the phone does itself, into the Downloads folder.",
        "reasons": {
            "ok": "The file is in Downloads.",
            "invalid": "The address is not an http:// or https:// one.",
            "no_space": "The phone ran out of room.",
            "failed": "The server refused or the connection did not last.",
            "unavailable": "The phone's download service is switched off.",
        },
        "verbs": {
            "start": Verb(LATER, [_p("url"), _p("name", "text", ""), _p("title", "text", "")],
                          java="start", needs=("internet",),
                          says="Download in the background, with the system's notification."),
        },
    },
    "calendar": {
        "class": "ApkpyHandoff",
        "says": "An event, written into the phone's calendar app for the person to save.",
        "reasons": {
            "ok": "The calendar opened with the event filled in.",
            "invalid": "start= or end= is not a date ApkPy reads, or the end is before the start.",
            "no_app": "No calendar app is installed.",
        },
        "verbs": {
            "add_event": Verb(DO, [_p("title"), _p("start"), _p("end", "text", ""),
                                   _p("location", "text", ""), _p("notes", "text", ""),
                                   _p("all_day", "bool", False)],
                              java="addEvent",
                              says="Open the calendar's new-event screen, filled in."),
        },
    },
    "phone": {
        "class": "ApkpyHandoff",
        "says": "The dialler and the messages app, with the number already typed.",
        "reasons": {
            "ok": "The other app opened.",
            "invalid": "There is no number to dial or write to.",
            "no_app": "This device has no dialler or no messages app.",
        },
        "verbs": {
            "dial": Verb(DO, [_p("number")], java="dial",
                         says="Open the dialler on this number; the person presses call."),
            "sms": Verb(DO, [_p("number"), _p("text", "text", "")], java="sms",
                        says="Open a message to this number; the person presses send."),
        },
    },
    "recorder": {
        "class": "ApkpyRecorder",
        "says": "The microphone, recorded into a file of the app.",
        "reasons": {
            "ok": "It is recording.",
            "busy": "It was recording already.",
            "permission_denied": "The person did not allow the microphone.",
            "permission_blocked": "The microphone is refused for good; only the phone's settings change that.",
            "no_microphone": "This device has no microphone.",
            "failed": "The microphone could not be started -- another app may be holding it.",
        },
        "verbs": {
            "start": Verb(LATER, java="start", needs=("launcher", "microphone"),
                          says="Ask for the microphone if needed, and start recording."),
            "stop": Verb(VALUE, java="stop",
                         says="Stop, and answer the path of the file (\"\" when nothing was recorded)."),
            "is_recording": Verb(FLAG, java="isRecording",
                                 says="Whether it is recording right now."),
            "seconds": Verb(VALUE, java="seconds",
                            says="How long it has been recording, in whole seconds."),
        },
    },
    "printing": {
        "class": "ApkpyPrinting",
        "says": "Android's print screen: any printer, or Save as PDF.",
        "reasons": {
            "ok": "The print screen opened with the document.",
            "unavailable": "This device cannot print.",
            "failed": "The document could not be laid out.",
        },
        "verbs": {
            "html": Verb(LATER, [_p("html"), _p("name", "text", "Document")],
                         java="html", says="Print a document written in HTML."),
            "text": Verb(LATER, [_p("text"), _p("name", "text", "Document")],
                         java="text", says="Print plain text as it is."),
        },
    },
    "incoming": {
        "class": "ApkpyIncoming",
        "says": "What opened the app from outside: a link, or something shared into it.",
        "reasons": {
            "ok": "Forgotten.",
        },
        "verbs": {
            "links": Verb(DECLARE, [_p("scheme"), _p("host", "text", ""),
                                    _p("preview", "text", "")],
                          needs=("incoming",),
                          says="Addresses that open this app."),
            "shares": Verb(DECLARE, [_p("kind", "text", "text"), _p("preview", "text", "")],
                           needs=("incoming",),
                           says="What other apps can share into this one."),
            "link": Verb(VALUE, java="link", needs=("incoming",),
                         says="The address that opened the app, or \"\"."),
            "text": Verb(VALUE, java="text", needs=("incoming",),
                         says="The text another app shared, or \"\"."),
            "file": Verb(VALUE, java="file", needs=("incoming",),
                         says="The path of a copy of the file another app shared, or \"\"."),
            "clear": Verb(DO, java="clear", needs=("incoming",),
                          says="Forget what arrived, once the app has dealt with it."),
        },
    },
    "home_widget": {
        "class": "ApkpyWidget",
        "says": "A widget of the app on the phone's home screen.",
        "reasons": {
            "ok": "Done: the widget shows it, or the launcher is asking where to put it.",
            "unsupported": "This launcher does not take the offer; the person adds the "
                           "widget from the launcher's own list.",
        },
        "verbs": {
            "define": Verb(DECLARE, [_p("title"), _p("text", "text", ""),
                                     _p("caption", "text", ""), _p("icon", "text", ""),
                                     _p("name", "text", "")],
                           needs=("widget",),
                           says="That the app has a widget, and what it shows before "
                                "the app has said anything."),
            "set": Verb(DO, [_p("text"), _p("caption", "text", ""), _p("title", "text", "")],
                        java="set", needs=("widget",),
                        says="What the widget shows from now on."),
            "count": Verb(VALUE, java="count", needs=("widget",),
                          says="How many of them are on the home screen."),
            "pin": Verb(DO, java="pin", needs=("widget",),
                        says="Ask the launcher to put one on the home screen."),
        },
    },
    "quick_tile": {
        "class": "ApkpyTile",
        "says": "A tile of the app in the phone's quick settings.",
        "reasons": {
            "ok": "Done.",
            "added": "The tile is in quick settings now.",
            "already": "It was there already.",
            "dismissed": "The person said no.",
            "unsupported": "Before Android 13 an app cannot offer its tile; the person "
                           "adds it by editing quick settings.",
        },
        "verbs": {
            "define": Verb(DECLARE, [_p("label"), _p("icon", "text", ""),
                                     _p("preview", "bool", False)],
                           needs=("tile",),
                           says="That the app has a tile, and what it is called."),
            "set": Verb(DO, [_p("active", "bool", True), _p("subtitle", "text", "")],
                        java="set", needs=("tile",),
                        says="Whether the tile is lit, and the line under its name."),
            "is_active": Verb(FLAG, java="isActive", needs=("tile",),
                              says="Whether the tile is lit."),
            "opened": Verb(FLAG, java="opened", needs=("tile",),
                           says="Whether a tap on the tile is what opened the app."),
            "clear": Verb(DO, java="clear", needs=("tile",),
                          says="Forget that the tile opened the app, once it is dealt with."),
            "offer": Verb(LATER, java="offer", needs=("tile",),
                          says="Ask the person to add the tile to quick settings."),
        },
    },
    "ads": {
        "class": "ApkpyAds",
        "says": "Google AdMob: a banner, an ad between two screens, an ad for a reward.",
        "reasons": {
            "ok": "Done: the banner has its place, or the question of consent is settled.",
            "closed": "The ad was shown and the person closed it.",
            "skipped": "The person closed the ad before the reward.",
            "not_ready": "The ad took too long to arrive. It is kept, and the next "
                         "call shows it at once.",
            "no_fill": "There was no ad to show this time.",
            "network": "There is no connection.",
            "invalid": "The ad unit is not one AdMob knows.",
            "failed": "The ad could not be loaded or shown, or the person has not "
                      "answered the question of consent.",
        },
        "verbs": {
            "setup": Verb(DECLARE, [_p("app_id")], needs=("ads",),
                          says="The app's AdMob id. \"test\" is Google's own sample."),
            "banner": Verb(DO, [_p("unit"), _p("position", "text", "bottom")],
                           java="banner", needs=("ads",),
                           says="A banner along the bottom of this screen, or the top."),
            "hide_banner": Verb(DO, java="hideBanner", needs=("ads",),
                                says="Take the banner away."),
            "prepare": Verb(DO, [_p("interstitial", "text", ""), _p("rewarded", "text", "")],
                            java="prepare", needs=("ads",),
                            says="Fetch these ahead, so they open the moment they are "
                                 "asked for."),
            "interstitial": Verb(LATER, [_p("unit")], java="interstitial", needs=("ads",),
                                 says="A full-screen ad, at a pause in the app."),
            "rewarded": Verb(LATER, [_p("unit")], java="rewarded", needs=("ads",),
                             says="An ad the person chooses to watch. Answers the "
                                  "reward's amount."),
            "consent": Verb(LATER, java="consent", needs=("ads",),
                            says="Ask what the law where the person lives says to ask."),
            "needs_privacy_options": Verb(FLAG, java="needsPrivacyOptions", needs=("ads",),
                                          says="Whether the app has to offer a way back "
                                               "to that question."),
            "privacy_options": Verb(LATER, java="privacyOptions", needs=("ads",),
                                    says="Open the question again, for the person to "
                                         "change their answer."),
        },
    },
    "updates": {
        "class": "ApkpyUpdates",
        "says": "A newer version of the app, taken from Google Play without leaving it.",
        "reasons": {
            "available": "Play has a newer version than the one running.",
            "none": "This is the newest version.",
            "downloaded": "The new version is on the phone, waiting for install().",
            "ok": "The app is restarting into the new version.",
            "nothing": "There is no downloaded update to install.",
            "cancelled": "The person said not now.",
            "not_allowed": "Play does not offer this kind of update for this version.",
            "not_from_play": "This copy of the app did not come from Google Play.",
            "failed": "Play could not be asked, or the download did not finish.",
        },
        "verbs": {
            "check": Verb(LATER, java="check", needs=("updates",),
                          says="Ask Play whether there is a newer version."),
            "start": Verb(LATER, [_p("mode", "text", "flexible")], java="start",
                          needs=("updates",),
                          says="Download it: in the background, or over the whole screen."),
            "install": Verb(DO, java="install", needs=("updates",),
                            says="Restart into the version that was downloaded."),
        },
    },
    "health": {
        "class": "ApkpyHealth",
        "says": "What the phone's health records say: steps, heart rate, sleep.",
        "reasons": {
            "ok": "The person allowed everything that was asked for.",
            "denied": "The person did not allow all of it.",
            "no_permission": "The app has not been allowed to read this.",
            "no_data": "Nothing was recorded in that time.",
            "unavailable": "This phone has no Health Connect (it came with Android 14).",
            "invalid": "The time is not one ApkPy reads, or the end is before the start.",
            "failed": "Health Connect did not answer.",
        },
        "verbs": {
            "policy": Verb(DECLARE, [_p("url")], needs=("health",),
                           says="Where the app's privacy policy is. Health Connect "
                                "shows it, and allows nothing without it."),
            "available": Verb(FLAG, java="available", needs=("health",),
                              says="Whether this phone keeps health records an app can ask for."),
            "allowed": Verb(FLAG, [_p("kind")], java="allowed", needs=("health",),
                            says="Whether the app may read this."),
            "ask": Verb(LATER, [_p("kinds")], java="ask", needs=("health", "launcher"),
                        says="Ask the person to let the app read these."),
            "read": Verb(LATER, [_p("kind"), _p("start", "text", ""), _p("end", "text", "")],
                         java="read", needs=("health",),
                         says="The total, or the average, between two moments -- today "
                              "when none is given."),
        },
    },
    "timer": {
        "class": "ApkpyTimers",
        "says": "A function of the app run later, or again and again, while its "
                "screen is on show.",
        "reasons": {
            "ok": "The timer was started, or it was stopped.",
            "invalid": "The time is not a number of seconds, or it is below zero.",
            "not_running": "That function had no timer waiting on this screen.",
        },
        "verbs": {
            "after": Verb(DO, [_p("seconds", "number"), _p("run", "function")],
                          java="after",
                          says="Run the function once, this many seconds from now."),
            "every": Verb(DO, [_p("seconds", "number"), _p("run", "function")],
                          java="every",
                          says="Run the function again and again, this many seconds apart."),
            "cancel": Verb(DO, [_p("run", "function")], java="cancel",
                           says="Stop the timer of that function."),
            "running": Verb(FLAG, [_p("run", "function")], java="running",
                            says="Whether that function has a timer waiting."),
        },
    },
    "network": {
        "class": "ApkpyNetwork",
        "says": "Whether the phone reaches the internet, over what, and being "
                "told when that changes.",
        "reasons": {
            "ok": "The function is called from now on, when the connection changes.",
            "failed": "The phone would not say when the connection changes.",
        },
        "verbs": {
            "online": Verb(FLAG, java="online", needs=("network_state",),
                           says="Whether the phone reaches the internet right now."),
            "kind": Verb(VALUE, java="kind", needs=("network_state",),
                         says="What the connection is: \"wifi\", \"mobile\", "
                              "\"ethernet\", \"other\" or \"none\"."),
            "metered": Verb(FLAG, java="metered", needs=("network_state",),
                            says="Whether the person pays for what goes over it: "
                                 "mobile data, a phone shared as a hotspot."),
            "on_change": Verb(DO, [_p("run", "function")], java="onChange",
                              needs=("network_state",),
                              says="Call the function whenever one of those three "
                                   "answers changes, while its screen is on show."),
        },
    },
    "display": {
        "class": "ApkpyDisplay",
        "says": "What the phone's screen does while one of the app's screens is "
                "on show: staying on, how bright, the bars, which way up.",
        "reasons": {
            "ok": "The phone was asked to.",
            "invalid": "The brightness is not a number from 0 to 1 or \"auto\", or "
                       "the orientation is not \"portrait\", \"landscape\" or \"auto\".",
        },
        "verbs": {
            "keep_on": Verb(DO, [_p("on", "bool", True)], java="keepOn",
                            says="Keep the phone from dimming and locking while this "
                                 "screen is on show."),
            "brightness": Verb(DO, [_p("level")], java="brightness",
                               says="How bright the phone is while this screen is on "
                                    "show: from 0 to 1, or \"auto\" for the phone's own."),
            "immersive": Verb(DO, [_p("on", "bool", True)], java="immersive",
                              says="Hide the status bar and the navigation bar; a swipe "
                                   "from the edge shows them for a moment."),
            "orientation": Verb(DO, [_p("kind")], java="orientation",
                                says="Which way up this screen is: \"portrait\", "
                                     "\"landscape\", or \"auto\" to turn with the phone."),
        },
    },
    "app_lock": {
        "class": "ApkpyAppLock",
        "says": "The app locks itself after a while away or untouched, and the "
                "phone's own screen lock opens it again.",
        "reasons": {
            "ok": "The rule was kept, the app was locked, or the rule was taken away.",
            "invalid": "The minutes are not a number, or are below zero.",
            "no_lock": "This phone has no screen lock -- no PIN, pattern, password, "
                       "fingerprint or face -- so nothing could open the app again, "
                       "and it is not locked. A rule given to after() is kept, and "
                       "holds once the person sets one.",
        },
        "verbs": {
            "after": Verb(DO, [_p("minutes", "number"), _p("title", "text", "")],
                          java="after", needs=("app_lock",),
                          says="Lock the app once it has been away, or untouched, for "
                               "this many minutes; 0 locks it every time it comes back."),
            "now": Verb(DO, java="now", needs=("app_lock",),
                        says="Lock the app now."),
            "off": Verb(DO, java="off", needs=("app_lock",),
                        says="No more locking: the rule is taken away and the app opened."),
            "locked": Verb(FLAG, java="locked", needs=("app_lock",),
                           says="Whether the app is locked right now."),
        },
    },
}

# A family that needs a line at the top of the file before any of its calls
# means anything: family -> (the declaration, why, what to write).
DECLARED_BY = {
    "home_widget": ("define", "this app has no widget",
                    'home_widget.define("Steps", "0", caption="today", icon="directions_walk")'),
    "quick_tile": ("define", "this app has no tile",
                   'quick_tile.define("Focus", icon="timer")'),
    "ads": ("setup", "AdMob does not know which app this is",
            'ads.setup("test")   # your own id from AdMob, before release'),
    "health": ("policy", "Health Connect allows nothing to an app with no privacy "
                         "policy to show",
               'health.policy("https://example.com/privacy")'),
}

# health.read(kind): the permission Health Connect names for it, what the
# number is, the icon the Previewer draws beside it, and the number the
# Previewer answers -- a desk has no body, so it is a plausible day.
HEALTH_KINDS = {
    "steps": ("READ_STEPS", "steps", "directions_walk", "6482"),
    "distance": ("READ_DISTANCE", "metres", "straighten", "4310"),
    "active_calories": ("READ_ACTIVE_CALORIES_BURNED", "kilocalories",
                        "local_fire_department", "412"),
    "calories": ("READ_TOTAL_CALORIES_BURNED", "kilocalories", "restaurant", "1986"),
    "heart_rate": ("READ_HEART_RATE", "beats a minute, on average", "favorite", "68"),
    "resting_heart_rate": ("READ_RESTING_HEART_RATE", "beats a minute, on average",
                           "favorite_border", "57"),
    "sleep": ("READ_SLEEP", "minutes", "bedtime", "437"),
    "weight": ("READ_WEIGHT", "kilograms, on average", "monitor_weight", "72.4"),
    "floors": ("READ_FLOORS_CLIMBED", "floors", "stairs", "9"),
    "exercise": ("READ_EXERCISE", "minutes", "fitness_center", "38"),
    "hydration": ("READ_HYDRATION", "litres", "water_drop", "1.25"),
}

# Google's own sample ids: they always answer with an ad marked "Test Ad", and
# clicking one costs nobody anything. What "test" stands for.
ADS_TEST = {
    "app": "ca-app-pub-3940256099942544~3347511713",
    "banner": "ca-app-pub-3940256099942544/9214589741",
    "interstitial": "ca-app-pub-3940256099942544/1033173712",
    "rewarded": "ca-app-pub-3940256099942544/5224354917",
}
AD_POSITIONS = ("bottom", "top")
UPDATE_MODES = ("flexible", "immediate")
# What Google's sample rewarded ad gives, and so what the Previewer answers.
AD_REWARD = "10"

# The kinds that are an average over the period. The rest are a total, and a
# total of nothing is 0; an average of nothing is no number at all.
HEALTH_AVERAGES = ("heart_rate", "resting_heart_rate", "weight")

# The libraries a family brings into the app, and only when it is used.
GRADLE = {
    "ads": ("implementation 'com.google.android.gms:play-services-ads:25.5.0'",
            "implementation 'com.google.android.ump:user-messaging-platform:4.0.0'"),
    "updates": ("implementation 'com.google.android.play:app-update:2.1.0'",),
}

# What a share can be, and the MIME type the manifest names for it.
SHARE_KINDS = {"text": "text/plain", "image": "image/*", "file": "*/*"}

# haptics.<kind>() -> android.view.HapticFeedbackConstants, and what a phone
# older than Android 11 (which has no CONFIRM and no REJECT) does instead.
FEEDBACK = {
    "tap": ("VIRTUAL_KEY", "VIRTUAL_KEY"),
    "tick": ("CLOCK_TICK", "CLOCK_TICK"),
    "heavy": ("LONG_PRESS", "LONG_PRESS"),
    "success": ("CONFIRM", "VIRTUAL_KEY"),
    "error": ("REJECT", "LONG_PRESS"),
}

# The ranges a number is kept inside, on both sides.
LIMITS = {
    "vibrate_ms": (1, 5000),
    "rate": (0.25, 4.0),
    "pitch": (0.5, 2.0),
}

# Schemes that already belong to the phone: an app that claimed one would be
# offered every time somebody tapped a telephone number.
RESERVED_SCHEMES = frozenset({
    "tel", "sms", "smsto", "mms", "mmsto", "mailto", "geo", "file", "content",
    "data", "javascript", "about", "intent", "market", "android-app",
})


def namespaces():
    return tuple(SPEC)


def verb(namespace, name):
    """The :class:`Verb`, or ``None``."""
    return SPEC.get(namespace, {}).get("verbs", {}).get(name)


def verbs(namespace):
    return tuple(SPEC.get(namespace, {}).get("verbs", {}))


def reasons(namespace):
    return dict(SPEC.get(namespace, {}).get("reasons", {}))


def label(namespace, name):
    return "%s.%s()" % (namespace, name)


def signature(namespace, name):
    """``speech.say(text, language="", rate=1.0, pitch=1.0, on_result=None)``."""
    found = verb(namespace, name)
    parts = []
    for argument, _kind, default in found.params:
        parts.append(argument if default is REQUIRED else "%s=%r" % (argument, default))
    if found.mode == LATER:
        parts.append("on_result=None")
    return "%s.%s(%s)" % (namespace, name, ", ".join(parts).replace("'", '"'))


def unknown(namespace, name):
    """What to say of ``haptics.buzz()``: the arguments of :func:`refuse`.

    The build says it with the line; the Previewer says it when the call is
    reached. One sentence, so neither has to be learnt twice.
    """
    import difflib
    known = list(verbs(namespace))
    close = difflib.get_close_matches(name, known, n=2, cutoff=0.5)
    hints = ["Did you mean %s?" % signature(namespace, match) for match in close]
    hints.append("%s has: %s." % (namespace, ", ".join(verb + "()" for verb in known)))
    return {
        "message": "%s has no %s()" % (namespace, name),
        "received": "%s.%s(...)" % (namespace, name),
        "suggestions": hints,
        "expected": " / ".join(signature(namespace, verb) for verb in known[:3]),
    }


def refuse(message, received="", line=0, cause="", suggestions=(), expected="", error=None,
           docs=""):
    """One error shape for every mistake in one of these calls.

    ``error`` is the class to raise when it has to be more than an
    ``ApkpyError`` -- see ``features/kit.py``, where a missing call must stay
    an ``AttributeError`` too. ``docs`` is the page to send the reader to
    when the message does not open with the family it is about.
    """
    from .diagnostics import ApkpyError
    raise (error or ApkpyError)(
        message,
        code=CODE,
        title="A call to the phone that ApkPy cannot build",
        cause=cause or ("These calls are written into the app when it is built, "
                        "so each one has to be a call ApkPy knows, with the "
                        "arguments it takes."),
        expected=expected,
        received=received,
        suggestions=list(suggestions),
        docs=docs or docs_for(message),
        line=line or 0,
    )


# ── what the text is read as ─────────────────────────────────────────────────

_NUMBER = re.compile(native_rules.NUMBER)
_EDGES = "".join(chr(code) for code in range(33))


def trim(text):
    """Without what Java's ``trim()`` takes off: everything up to the space.
    Python's ``strip()`` also takes Unicode's other spaces, and a rule both
    sides follow cannot depend on which side read the text."""
    return "" if text is None else str(text).strip(_EDGES)


def number(text, fallback):
    """The number in ``text``, or ``fallback`` when it is not one. A call to
    the phone never stops the app over a number: the worst a wrong one does
    is the ordinary thing."""
    trimmed = trim(text)
    if isinstance(text, bool) or not _NUMBER.fullmatch(trimmed):
        return float(fallback)
    value = float(trimmed)
    if value != value or value in (float("inf"), float("-inf")):
        return float(fallback)
    return value


def whole(text, fallback):
    """The nearest whole number, halves to even -- Python's ``round`` and
    Java's ``Math.rint``, which is the rounding the rest of ApkPy uses."""
    value = number(text, fallback)
    if abs(value) >= 9.0e18:
        return int(fallback)
    return int(round(value))


def truth(text):
    """``"true"`` in any case is true; everything else is not."""
    return trim(text).lower() == "true"


def flag(value):
    """How a yes/no is spelt once it is text: Python's own way."""
    return "True" if value else "False"


def clamp(value, low, high):
    return max(low, min(high, value))


# A moment, the way datetime.now() writes it -- and the shorter ways a person
# would type it. Seconds are optional, so is the time, and a T may stand where
# the space is.
_WHEN = re.compile(
    r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})"
    r"(?:[ T]([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?)?")


def when(text):
    """``"2026-11-03 15:30"`` -> ``(datetime, has_time)``, or ``None``.

    The time is the phone's own: no zone is written, because the person
    typing "half past three" means half past three where they are.
    """
    found = _WHEN.fullmatch(trim(text))
    if not found:
        return None
    year, month, day, hour, minute, second = found.groups()
    has_time = hour is not None
    try:
        moment = _datetime.datetime(
            int(year), int(month), int(day),
            int(hour or 0), int(minute or 0), int(second or 0))
    except ValueError:
        return None
    return moment, has_time


def event_times(start, end, all_day):
    """What ``calendar.add_event`` makes of its three time arguments:
    ``(begin, finish, all_day)`` or ``None`` when they cannot be read.

    No time in ``start`` means the whole day. No ``end`` means an hour, or
    the one day. An all-day event ends at the start of the day after its
    last, which is how a calendar stores "the 3rd to the 5th".
    """
    first = when(start)
    if first is None:
        return None
    begin, has_time = first
    whole_day = truth(all_day) or not has_time
    if whole_day:
        begin = begin.replace(hour=0, minute=0, second=0)
    if trim(end):
        last = when(end)
        if last is None:
            return None
        finish = last[0]
        if whole_day:
            finish = finish.replace(hour=0, minute=0, second=0) + _datetime.timedelta(days=1)
    else:
        finish = begin + (_datetime.timedelta(days=1) if whole_day
                          else _datetime.timedelta(hours=1))
    if finish <= begin:
        return None
    return begin, finish, whole_day


# ASCII on purpose, like the digits above: \s is every script's spaces in
# Python and six characters in Java.
WEB = r"(?i)https?://[^\s/]+\S*"
_WEB = re.compile(WEB, re.ASCII)
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*")
_HOST = re.compile(r"(?:\*\.)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?")


# What HTML written by an app looks like before the app styles it. A page shown
# inside the app wears the app's own colours; a printed one is ink on paper.
# Both sides wrap the same markup in the same rules, so the page the Previewer
# opens in the browser is the one the phone draws. Rules of the app's own, in
# a <style> of its markup, come later in the page and win.
PAGE_CSS = (
    "html{-webkit-text-size-adjust:100%}"
    "body{margin:0;padding:20px 20px 32px;"
    "font:16px/1.55 system-ui,-apple-system,Roboto,sans-serif;"
    "color:@ink@;background:@surface@;overflow-wrap:anywhere}"
    "h1{font-size:26px;line-height:1.2;margin:4px 0 14px}"
    "h2{font-size:20px;line-height:1.25;margin:26px 0 10px}"
    "h3{font-size:17px;line-height:1.3;margin:22px 0 8px}"
    "p,ul,ol{margin:0 0 14px}"
    "a{color:@accent@}"
    "img,video{max-width:100%;height:auto}"
    "table{border-collapse:collapse;max-width:100%}"
    "td,th{padding:6px 10px;text-align:left}"
    "pre{overflow-x:auto}"
)
PRINT_CSS = (
    "body{margin:0;padding:14mm;font:11pt/1.5 sans-serif;color:#111;background:#fff}"
    "h1{font-size:20pt;line-height:1.2;margin:0 0 10pt}"
    "h2{font-size:15pt;line-height:1.25;margin:16pt 0 6pt}"
    "h3{font-size:12pt;margin:12pt 0 4pt}"
    "p,ul,ol{margin:0 0 8pt}"
    "table{border-collapse:collapse}"
    "td,th{padding:4pt 8pt;text-align:left}"
    "img{max-width:100%}"
    ".apkpy-text{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:0}"
)
_WHOLE_PAGE = re.compile("<html", re.ASCII | re.IGNORECASE)


def page_css(surface, ink, accent):
    """The rules for a page shown inside the app, in the app's colours."""
    return (PAGE_CSS.replace("@surface@", surface).replace("@ink@", ink)
            .replace("@accent@", accent))


def document(markup, css):
    """HTML an app wrote, as a whole page.

    A fragment -- ``<h1>Terms</h1><p>...</p>`` -- is given a head and these
    rules. Markup that is a page already is the author's, and is left alone.
    """
    text = "" if markup is None else str(markup)
    if _WHOLE_PAGE.search(text):
        return text
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<style>" + css + "</style></head><body>" + text + "</body></html>")


_AD_APP = re.compile(r"ca-app-pub-[0-9]{16}~[0-9]{10}")
_AD_UNIT = re.compile(r"ca-app-pub-[0-9]{16}/[0-9]{10}")


def ad_app_id(text):
    """The AdMob app id, ``"test"`` for Google's sample, or ``""``."""
    given = trim(text)
    if given == "test":
        return ADS_TEST["app"]
    return given if _AD_APP.fullmatch(given) else ""


def ad_unit(text, kind):
    """The ad unit id, ``"test"`` for Google's sample of that kind, or ``""``."""
    given = trim(text)
    if given == "test":
        return ADS_TEST[kind]
    return given if _AD_UNIT.fullmatch(given) else ""


def health_kinds(text):
    """``"steps, heart_rate"`` -> ``["steps", "heart_rate"]``, each once, in the
    order written. A word that is not a kind is answered as ``(None, word)``.
    """
    found = []
    for word in str("" if text is None else text).split(","):
        kind = trim(word)
        if not kind:
            continue
        if kind not in HEALTH_KINDS:
            return None, kind
        if kind not in found:
            found.append(kind)
    return found, ""


def health_value(kind, number):
    """A reading as the text an app gets: whole, except what is weighed or
    poured."""
    if kind == "weight":
        return "%.1f" % float(number)
    if kind == "hydration":
        return "%.2f" % float(number)
    return str(int(round(float(number))))


def health_period(start, end, now):
    """What ``health.read`` makes of its two times: ``(begin, finish)``, or
    ``None`` when they cannot be read or the end is not after the start.

    Nothing given is today so far. A start with no hour is that day's
    midnight; an end with no hour is the whole of that day. No end is now.
    """
    given_start, given_end = trim(start), trim(end)
    if given_start:
        first = when(given_start)
        if first is None:
            return None
        begin = first[0]
    else:
        begin = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if given_end:
        last = when(given_end)
        if last is None:
            return None
        finish = last[0] if last[1] else last[0] + _datetime.timedelta(days=1)
    else:
        finish = now
        if not given_start and finish <= begin:
            # Asked at midnight exactly: today has only just begun.
            finish = begin + _datetime.timedelta(seconds=1)
    if finish <= begin:
        return None
    return begin, finish


def health_sample(kind, begin, finish):
    """What the Previewer answers for a reading: a desk has no body, so it is
    a plausible one. The same day always gives the same number, and no two
    days quite the same, so a week of them draws like a week."""
    usual = float(HEALTH_KINDS[kind][3])
    days = max(1, int(-(-(finish - begin).total_seconds() // 86400)))
    total = 0.0
    for offset in range(min(days, 366)):
        day = (begin + _datetime.timedelta(days=offset)).toordinal()
        # A fixed scramble of the day's number, spread over 0.80 .. 1.20.
        spread = ((day * 2654435761 + len(kind) * 40503) % 1000) / 1000.0
        # Each day as it would be answered on its own, so a week read in one
        # go is the sum of its seven days read one by one.
        total += float(health_value(kind, usual * (0.80 + 0.40 * spread)))
    if kind in HEALTH_AVERAGES:
        total /= min(days, 366)
    return health_value(kind, total)


def web_address(text):
    """The address when it is an http(s) one, else ``""``."""
    trimmed = trim(text)
    return trimmed if _WEB.fullmatch(trimmed) else ""


def link_scheme(scheme, host=""):
    """Why ``incoming.links(scheme, host)`` cannot be built, or ``""``."""
    scheme, host = str(scheme or ""), str(host or "")
    if not _SCHEME.fullmatch(scheme):
        return ("a scheme is lower-case letters, digits, + . and -, starting "
                "with a letter: \"notes\", not %r" % scheme)
    if scheme in RESERVED_SCHEMES:
        return "%s: already belongs to the phone" % scheme
    if scheme in ("http", "https") and not host:
        return ("%s needs the site as well, or the app would be offered for "
                "every page on the web" % scheme)
    if host and not _HOST.fullmatch(host):
        return "%r is not a host name: write it like \"example.com\"" % host
    return ""


def phone_number(text):
    """The number as the dialler takes it: digits, and the few signs a number
    is written with. ``""`` when nothing of a number is left."""
    kept = "".join(ch for ch in ("" if text is None else str(text))
                   if ch in "0123456789+*#,;")
    return kept if any(ch.isdigit() for ch in kept) else ""


# What a file in the app's folder may be called. On the phone that folder is
# Android's; on the desk it is Windows' or macOS'. A name one of them cannot
# write is refused by both, so an app that works in the Previewer works built.
_FILE_FORBIDDEN = '<>:"|?*\\'
_FILE_DEVICES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + ["COM%d" % port for port in range(1, 10)]
    + ["LPT%d" % port for port in range(1, 10)])


def file_name(text):
    """``notes.txt`` or ``drafts/monday.txt`` as given, or ``""`` when it is
    not the name of a file in the app's folder.

    A name is one part, or several joined by ``/`` (folders are made as
    needed). No part is empty, ``.`` or ``..`` -- so no name leaves the
    folder -- or begins or ends with a space, or ends with a dot, or holds
    one of ``< > : " | ? * \\`` or a control character, or is one of the
    names Windows keeps for devices, or is longer than 255 bytes. A part
    that begins with ``.apkpy-`` is ApkPy's own.
    """
    given = trim(text)
    if not given:
        return ""
    for part in given.split("/"):
        if not part or part in (".", ".."):
            return ""
        if part[0] == " " or part[-1] in " .":
            return ""
        if any(ord(ch) < 32 or ord(ch) == 127 or ch in _FILE_FORBIDDEN for ch in part):
            return ""
        if part.split(".")[0].upper() in _FILE_DEVICES or part.startswith(".apkpy-"):
            return ""
        if len(part.encode("utf-8", "replace")) > 255:
            return ""
    return given


# ── timers ───────────────────────────────────────────────────────────────────

# An every() never runs more often than this, and no timer waits longer than
# a week: a screen is not on show for longer, and both sides count in whole
# milliseconds that have to fit where they are kept.
TIMER_SHORTEST = 50
TIMER_LONGEST = 7 * 24 * 60 * 60 * 1000


def timer_millis(seconds, repeating):
    """``seconds`` as the whole milliseconds a timer waits, or ``-1`` when it
    is not a time: not a number, or below zero."""
    value = number(seconds, -1.0)
    if value < 0:
        return -1
    millis = int(round(min(value * 1000.0, float(TIMER_LONGEST))))
    return max(TIMER_SHORTEST, millis) if repeating else millis


def timer_next(due, period, now):
    """When an ``every()`` runs next, having just run at ``now`` what was due
    at ``due``.

    Its moments are a grid that starts when the timer was started, so a run
    that came a little late does not push the others late -- a clock that
    ticks once a second stays on the second.

    A run that came a whole period late or more is another matter: the screen
    was away. Moments that went by with nobody looking are not made up for,
    and the grid they belonged to is let go -- the timer goes on from here, a
    full period on. Kept to the old grid, the run that catches up and the
    next one could fall in the same second (seen on a phone: a countdown that
    took two steps at once on coming back), and a `timer.every(30, refresh)`
    asked the network twice in a row.
    """
    due, period, now = int(due), int(period), int(now)
    if now - due >= period:
        return now + period
    return due + period


def timer_example(label):
    """``timer.every(1, tick)`` or ``network.on_change(changed)``, for the errors."""
    if _watches(label):
        return label[:-1] + "changed)"
    return label[:-1] + ("tick)" if label.endswith("cancel()") or label.endswith("running()")
                         else "1, tick)")


def timer_not_a_function(label, written=""):
    """What to say when ``run=`` is not a function of the app: the arguments
    of :func:`refuse`. The build says it with the line and the Previewer when
    the call is reached, in the same words."""
    watches = _watches(label)
    return {
        "message": "%s: run= has to be a function you defined" % label,
        "cause": "%s A lambda, a method or what a call answers has no name of "
                 "its own to call."
                 % ("The function is called later, by its name, when the "
                    "connection changes." if watches else
                    "A timer calls the function later, by its name."),
        "received": written,
        "expected": timer_example(label),
        "suggestions": ["def %s(): ...   then   %s"
                        % ("changed" if watches else "tick", timer_example(label))],
    }


def timer_called(label, name):
    """``timer.every(1, tick())``: the brackets ran the function on the spot."""
    watches = _watches(label)
    example = timer_example(label).replace("changed" if watches else "tick", name)
    return {
        "message": "%s: %s() is called here, and %s is handed what it answers"
                   % (label, name, label if watches else "the timer"),
        "cause": "With the brackets the function runs now, once, and %s."
                 % ("nothing is left to call when the connection changes" if watches
                    else "the timer has nothing left to call"),
        "expected": example,
        "suggestions": ["Write the name alone: %s" % example],
    }


def timer_swapped(label, name):
    """``timer.every(tick, 1)``."""
    return {
        "message": "%s takes the seconds first, then the function" % label,
        "received": "%s%s, ...)" % (label[:-1], name),
        "expected": timer_example(label).replace("tick", name),
    }


def timer_takes_nothing(label, name, arguments):
    """The function a timer calls is called with nothing."""
    if _watches(label):
        return {
            "message": "%s() is called with nothing when the connection changes, "
                       "and it takes %s" % (name, ", ".join(arguments)),
            "cause": "It is only told that something changed. What changed is "
                     "what network.online() and network.kind() answer inside it.",
            "received": "def %s(%s)" % (name, ", ".join(arguments)),
            "expected": "def %s():" % name,
            "docs": docs_for(label),
        }
    return {
        "message": "%s() is called by a timer with nothing, and it takes %s"
                   % (name, ", ".join(arguments)),
        "cause": "A timer has nothing to hand over: it only says the time has come.",
        "received": "def %s(%s)" % (name, ", ".join(arguments)),
        "expected": "def %s():" % name,
        "docs": docs_for(label),
    }


def timer_at_the_top(label):
    """A timer started by a line at the top of the file."""
    return {
        "message": "%s at the top of the file starts before there is a screen" % label,
        "cause": "%s belongs to the screen that is on show when it is "
                 "started, and the lines at the top of the file run before any "
                 "screen is." % ("What is watched" if _watches(label) else "A timer"),
        "suggestions": ["Start it in a function the screen calls when it opens: "
                        "lifecycle(home, on_mount=start)",
                        "Or in the function of a button."],
    }


# ── the connection ───────────────────────────────────────────────────────────

# What network.kind() can answer, in the order they are asked: a phone on
# Wi-Fi behind a VPN is on Wi-Fi.
NETWORK_KINDS = ("wifi", "mobile", "ethernet", "other", "none")


def network_kind(connected, wifi, mobile, ethernet):
    """What the connection is, from what the phone says it is made of."""
    if not connected:
        return "none"
    if wifi:
        return "wifi"
    if mobile:
        return "mobile"
    if ethernet:
        return "ethernet"
    return "other"


def network_online(connected, internet, validated):
    """A connection reaches the internet when it is one that is meant to and
    the phone has seen it do so. A Wi-Fi that wants a login page first, or a
    router with no line behind it, is a connection that goes nowhere: it has
    a kind, and it is not online."""
    return bool(connected and internet and validated)


def network_metered(connected, unmetered):
    """Nothing is paid for a connection that is not there."""
    return bool(connected and not unmetered)


def network_state(online, kind, metered):
    """The three answers as one text. A screen's functions are called when
    this text is not the one they last heard, and for no other reason."""
    return "%s %s%s" % ("online" if online else "offline", kind,
                        " metered" if metered else "")


def _watches(label):
    """Whether the function handed to this call is one told of a change
    (``network.on_change``) rather than one a timer runs."""
    return not label.startswith("timer.")


# ── the display ──────────────────────────────────────────────────────────────

# Which way up a screen is. "auto" turns with the phone, as a screen that asks
# for nothing does.
ORIENTATIONS = ("auto", "portrait", "landscape")
# From this width in dp on its shorter side -- a tablet, a foldable opened
# out -- Android 16 turns every screen with the device, whatever the app asks:
# an app built for it (targetSdk 36) cannot hold one way up there. The
# Previewer follows the same rule for the device it stands in for.
LARGE_SCREEN = 600
# What display.brightness() is handed to give the level back to the phone, and
# the two numbers a level that is not one is read as.
BRIGHTNESS_AUTO = "auto"
BRIGHTNESS_OWN = -1.0
BRIGHTNESS_INVALID = -2.0


def _lower(text):
    """Lower case for A to Z and nothing else. Python and Java fold the rest
    of Unicode differently -- a dotted capital I is one letter to one and two
    to the other -- and a word of the table has none of it."""
    return "".join(chr(ord(letter) + 32) if "A" <= letter <= "Z" else letter
                   for letter in trim(text))


def display_orientation(text):
    """One of :data:`ORIENTATIONS`, or ``""`` when the text is none of them."""
    kind = _lower(text)
    return kind if kind in ORIENTATIONS else ""


def display_brightness(text):
    """The level in ``text``: 0.0 to 1.0, :data:`BRIGHTNESS_OWN` for
    ``"auto"`` -- the phone's own -- and :data:`BRIGHTNESS_INVALID` for
    anything else. A number outside 0 to 1 is not brought inside it: 90 is
    somebody who meant 0.9, and full brightness is not what to answer them."""
    if _lower(text) == BRIGHTNESS_AUTO:
        return BRIGHTNESS_OWN
    level = number(text, BRIGHTNESS_INVALID)
    if not 0.0 <= level <= 1.0:
        return BRIGHTNESS_INVALID
    return level + 0.0          # -0.0 is 0.0


def display_at_the_top(label):
    """``display.keep_on(True)`` on a line at the top of the file."""
    whole_app = label.startswith("display.orientation")
    return {
        "message": "%s at the top of the file runs before there is a screen" % label,
        "cause": "What is asked of the display belongs to the screen that is on "
                 "show when it is asked, and the lines at the top of the file run "
                 "before any screen is.",
        "suggestions": (["For every screen of the app: "
                         "run(start_screen=home, orientation=\"portrait\")"]
                        if whole_app else []) + [
            "Ask in a function the screen calls when it opens: "
            "lifecycle(home, on_mount=opened)",
            "Or in the function of a button."],
    }


def display_wrong_orientation(label, written):
    """An orientation that is none of the three, written out in the source."""
    return {
        "message": "%s: there is no orientation %r" % (label, written),
        "received": written,
        "suggestions": ["One of: %s." % ", ".join('"%s"' % kind for kind in ORIENTATIONS),
                        '"auto" turns with the phone, which is what a screen does '
                        "when it asks for nothing."],
    }


def display_wrong_brightness(label, written):
    """A level that is not one, written out in the source."""
    hints = ['0 is the darkest the phone goes and 1 the brightest; "auto" gives '
             "the level back to the phone."]
    percent = number(written, BRIGHTNESS_INVALID)
    if 1.0 < percent <= 100.0:
        hints.insert(0, "For %s%%, write %s." % (("%g" % percent), ("%g" % (percent / 100.0))))
    return {
        "message": "%s: level= is from 0 to 1 or \"auto\", got %r" % (label, written),
        "received": str(written),
        "suggestions": hints,
    }


# ── the app's own lock ───────────────────────────────────────────────────────

# What app_lock.after() is handed that is not a number of minutes.
APP_LOCK_INVALID = -1.0
# Where the Previewer keeps the rule, beside the app's own storage: on the
# phone it is a preferences file of its own, so storage.clear() leaves it.
APP_LOCK_FILE = "apkpy_app_lock.json"
# What the lock says, on the phone and in the Previewer. The app's name goes
# where %s is.
APP_LOCK_WORDS = {
    "title": "Unlock %s",
    "heading": "%s is locked",
    "line": "Use your fingerprint, face or screen lock to open it.",
    "button": "Unlock",
}


def app_lock_minutes(text):
    """The minutes in ``text``, 0 or more, or :data:`APP_LOCK_INVALID`.
    A part of a minute is a number of minutes too: 0.5 is half a minute."""
    minutes = number(text, APP_LOCK_INVALID)
    if minutes < 0.0:
        return APP_LOCK_INVALID
    return minutes + 0.0        # -0.0 is 0.0


def app_lock_due(left_at, now, minutes):
    """Whether an app with this rule is to be locked as it comes back.

    ``left_at`` is when it went from the front, in milliseconds of the wall
    clock -- 0 or less when that is not known: the app was in front when it
    stopped, or the rule was never told. ``now`` is the same clock. Not
    knowing, and a clock that went backwards, both lock: a lock that opens by
    mistake is worse than one asked for twice."""
    if left_at <= 0 or now < left_at:
        return True
    return (now - left_at) >= minutes * 60000.0


def app_lock_title(title, app_name):
    """The prompt's title: the app's own words, or "Unlock" and its name."""
    said = trim(title)
    return said or APP_LOCK_WORDS["title"] % (trim(app_name) or "the app")


def app_lock_heading(app_name):
    """What the cover says over the padlock."""
    name = trim(app_name)
    return APP_LOCK_WORDS["heading"] % name if name else "The app is locked"


def app_lock_at_the_top(label):
    """``app_lock.after(5)`` on a line at the top of the file."""
    return {
        "message": "%s at the top of the file runs before there is a screen" % label,
        "cause": "The lock is drawn over the screen on show and asks the phone's "
                 "own lock to open it again, and the lines at the top of the file "
                 "run before any screen is. Once said, the rule is kept on the "
                 "phone: every screen follows it, after the app is closed too.",
        "suggestions": [
            "Say it as the first screen opens: lifecycle(home, on_mount=opened)",
            "Or in the function of a switch, with app_lock.off() to undo it."],
    }


def app_lock_wrong_minutes(label, written):
    """Minutes that are not a number of minutes, written out in the source."""
    return {
        "message": "%s: minutes= is a number from 0, got %r" % (label, written),
        "received": str(written),
        "suggestions": ["0 locks it every time the app comes back; 5 after five "
                        "minutes away or untouched; 0.5 after half a minute."],
    }


def speaking_seconds(text, rate=1.0):
    """Roughly how long a voice takes over this text -- the Previewer has no
    voice, and has to answer on_result at a believable moment."""
    words = max(1, len(str(text or "").split()))
    return clamp(words / (2.6 * clamp(number(rate, 1.0), *LIMITS["rate"])), 0.4, 20.0)
