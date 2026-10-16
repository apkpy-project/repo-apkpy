# -*- coding: utf-8 -*-
"""Play billing: the acknowledge rule, and the words a purchase can end with."""

import json
import unittest

from apkpy_lib.core.features import billing as codegen
from apkpy_lib.core.compiler import translate_python_to_android

PACKAGE = "com.apkpy.app"


def _shared():
    return codegen.shared_class_java(PACKAGE)


APP = '''from apkpy_lib import Screen, billing, button, label, list_view, run
home = Screen(id="home")
shop = list_view([], id="shop", screen=home)
out = label("", id="out", screen=home)


def shown(ok, items):
    if ok:
        shop.set_items(items, title="title", subtitle="price")
    else:
        out.set_value(items)


def bought(ok, value):
    if ok:
        out.set_value("thanks")
    else:
        out.set_value(value)


def ask():
    billing.prices(["pro_unlock", "coins_100"], on_result=shown)


def subs():
    billing.prices(["monthly"], kind="subscription", on_result=shown)


def pro():
    billing.buy("pro_unlock", on_result=bought)


def coins():
    billing.buy("coins_100", consumable=True, on_result=bought)


def monthly():
    billing.subscribe("monthly", on_result=bought)


def restore():
    billing.owned(on_result=shown)


def spend():
    billing.consume("coins_100", on_result=bought)


button("1", id="b1", screen=home, command=ask)
button("2", id="b2", screen=home, command=subs)
button("3", id="b3", screen=home, command=pro)
button("4", id="b4", screen=home, command=coins)
button("5", id="b5", screen=home, command=monthly)
button("6", id="b6", screen=home, command=restore)
button("7", id="b7", screen=home, command=spend)
run(start_screen=home)
'''

APP_WITHOUT = '''from apkpy_lib import Screen, button, label, run, toast
home = Screen(id="home")
label("plain", id="t", screen=home)
button("Tap", id="go", screen=home, command=lambda: toast("hi"))
run(start_screen=home)
'''


def _java(source):
    files = translate_python_to_android(source)
    return "\n".join(b for n, b in files.items() if n.endswith(".java"))


def _manifest(source):
    return translate_python_to_android(source).get("AndroidManifest.xml", "")


def _calls(java, marker):
    return [l for l in java.splitlines() if marker in l and "private void" not in l]


class TheMoneyRuleTests(unittest.TestCase):
    """Google refunds anything left unacknowledged for three days."""

    def test_a_purchase_is_acknowledged_without_being_asked_to(self):
        shared = _shared()
        self.assertIn("acknowledgePurchase", shared)
        self.assertIn("isAcknowledged()", shared)

    def test_a_consumable_is_consumed_instead(self):
        # Consuming is what lets it be bought again, and it settles the
        # three-day clock at the same time.
        self.assertIn("consumeAsync", _shared())

    def test_settling_happens_before_the_app_is_told(self):
        # Reporting success first and acknowledging later would let an app
        # unlock something that is about to be refunded.
        shared = _shared()
        settle = shared[shared.index("private static void settle("):]
        settle = settle[:settle.index("private static String describe(")]
        self.assertLess(settle.index("acknowledgePurchase"),
                        settle.rindex('post(cb, true, json)'))

    def test_a_pending_purchase_is_not_a_purchase(self):
        # Cash and slow methods land here. Unlocking now means giving away
        # the goods for a payment that may never clear.
        shared = _shared()
        self.assertIn("PurchaseState.PENDING", shared)
        self.assertIn('post(cb, false, "pending")', shared)

    def test_pending_is_a_reason_an_app_can_read(self):
        self.assertIn("pending", codegen.REASONS)


class TheHoleFoundByReadingTests(unittest.TestCase):
    """A purchase made while the app was closed was never acknowledged.

    onPurchasesUpdated only fires while the app is listening. If it is killed
    mid-purchase -- or the person buys, backgrounds, and never returns for a
    while -- the purchase is only ever seen by queryPurchasesAsync. It was
    being reported as owned and left unsettled, so Google refunded it after
    three days: exactly the failure this feature claims to prevent, in the one
    case where nobody was watching.
    """

    def test_listing_purchases_settles_anything_unacknowledged(self):
        shared = _shared()
        self.assertIn("private static void rescue(", shared)
        collect = shared[shared.index("private static void collect("):]
        collect = collect[:collect.index("private static void rescue(")]
        self.assertIn("rescue(p);", collect)

    def test_the_rescue_only_touches_what_needs_it(self):
        shared = _shared()
        rescue = shared[shared.index("private static void rescue("):]
        rescue = rescue[:rescue.index("public static void consume(")]
        self.assertIn("if (purchase.isAcknowledged()) return;", rescue)
        self.assertIn("acknowledgePurchase", rescue)


class TheLeaksTests(unittest.TestCase):

    def test_settling_does_not_hold_a_context(self):
        # The purchases listener is static and lives as long as the process.
        # Handing it an Activity kept a dead screen alive.
        shared = _shared()
        self.assertIn(
            "private static void settle(final com.android.billingclient.api.Purchase",
            shared)

    def test_an_unready_client_is_closed_before_being_replaced(self):
        # Otherwise every retry leaves a service binding behind.
        shared = _shared()
        head = shared[:shared.index("public static String reasonFor")]
        with_client = shared[shared.index("private static void withClient("):]
        with_client = with_client[:with_client.index("private static void settle(")]
        self.assertIn("sClient.endConnection()", with_client)



class TheVocabularyTests(unittest.TestCase):

    def test_every_play_response_code_lands_in_the_table(self):
        for code in list(codegen._RESPONSE_CODES) + [99, -7]:
            self.assertIn(codegen.reason_for_code(code), codegen.REASONS)

    def test_the_generated_switch_carries_the_whole_table(self):
        shared = _shared()
        for code, reason in codegen._RESPONSE_CODES.items():
            self.assertIn('case %d: return "%s";' % (code, reason), shared)

    def test_the_previewer_reads_the_same_table(self):
        from apkpy_lib.features import billing as preview
        self.assertIs(preview.REASONS, codegen.REASONS)

    def test_already_owned_is_its_own_word(self):
        # Play refuses a second purchase; an app that shows "payment failed"
        # for it is lying to a paying customer.
        self.assertEqual(codegen.reason_for_code(7), "owned")

    def test_a_reason_is_never_empty(self):
        for reason in codegen.REASONS:
            self.assertTrue(reason.strip(), reason)


class TheServerSideTests(unittest.TestCase):

    def test_a_purchase_carries_the_token_that_a_server_can_check(self):
        # On-device state can be faked. The token is the only thing a backend
        # can verify against the Play Developer API.
        shared = _shared()
        describe = shared[shared.index("private static String describe("):]
        describe = describe[:describe.index("public static void prices(")]
        self.assertIn("token", describe)
        self.assertIn("getPurchaseToken()", describe)

    def test_owned_reports_the_token_too(self):
        shared = _shared()
        self.assertIn("getPurchaseToken()", shared)
        self.assertIn("describe(p)", shared)


class TheGeneratedAppTests(unittest.TestCase):

    def test_all_five_verbs_reach_the_activity(self):
        java = _java(APP)
        for marker in ("_billingPrices(", "_billingBuy(", "_billingOwned(",
                       "_billingConsume("):
            self.assertTrue(_calls(java, marker), marker)

    def test_it_survives_a_lambda_that_calls_a_helper(self):
        source = APP.replace("command=ask)", "command=lambda: ask())")
        self.assertTrue(_calls(_java(source), "_billingPrices("))

    def test_subscribe_cannot_be_launched_as_a_one_time_product(self):
        # Passing a subscription id to the one-time flow fails at Play with a
        # developer error, so the kind is decided by the verb.
        java = _java(APP)
        line = [l for l in _calls(java, "_billingBuy(") if "monthly" in l][0]
        self.assertIn('"subs"', line)

    def test_a_consumable_is_marked_at_the_call_site(self):
        java = _java(APP)
        line = [l for l in _calls(java, "_billingBuy(") if "coins_100" in l][0]
        self.assertIn("true", line)
        pro = [l for l in _calls(java, "_billingBuy(") if "pro_unlock" in l][0]
        self.assertIn("false", pro)

    def test_a_subscription_names_an_offer(self):
        # launchBillingFlow refuses a subscription with no offer token.
        self.assertIn("setOfferToken(", _shared())

    def test_prices_are_asked_for_rather_than_written_down(self):
        # A hardcoded price is wrong in most of the world.
        shared = _shared()
        self.assertIn("getFormattedPrice()", shared)

    def test_the_permission_is_not_put_under_android_permission(self):
        # com.android.vending.BILLING is not in that namespace, and prefixing
        # it produced a name no Android has heard of.
        manifest = _manifest(APP)
        self.assertIn(
            '<uses-permission android:name="com.android.vending.BILLING" />',
            manifest)
        self.assertNotIn("android.permission.com.android", manifest)

    def test_the_java_identifier_drops_the_package(self):
        from apkpy_lib.core.compiler import _permission_symbol
        self.assertEqual(_permission_symbol("com.android.vending.BILLING"),
                         "BILLING")
        self.assertIn("PERMISSION_REQ_BILLING", _java(APP))

    def test_an_app_that_sells_nothing_carries_none_of_it(self):
        java = _java(APP_WITHOUT)
        self.assertNotIn("BillingResultCallback", java)
        self.assertNotIn("billingclient", java)
        self.assertNotIn("BILLING", _manifest(APP_WITHOUT))

    def test_the_gradle_dependency_is_gated_on_the_class_it_emits(self):
        self.assertIn("com.android.billingclient.api.BillingClient", _java(APP))
        self.assertNotIn("com.android.billingclient", _java(APP_WITHOUT))

    def test_the_java_is_balanced(self):
        java = _java(APP)
        for opener, closer in (("{", "}"), ("(", ")")):
            self.assertEqual(java.count(opener), java.count(closer))


class TheDuplicateCallbackTests(unittest.TestCase):

    def test_several_purchases_in_one_update_report_once(self):
        # Play can hand back more than one purchase at a time. Reporting per
        # row fired the app's callback several times for a single tap.
        shared = _shared()
        self.assertIn("first ? waiting : null", shared)

    def test_the_client_and_the_pending_caller_are_volatile(self):
        shared = _shared()
        for field in ("sClient", "sPending", "sPendingConsumable"):
            matches = [l for l in shared.splitlines()
                       if (" " + field + ";") in l or (" " + field + " =") in l]
            self.assertIn("volatile", matches[0], field)



class ThePreviewerTests(unittest.TestCase):

    def setUp(self):
        from apkpy_lib.features import billing as preview
        preview._owned.clear()

    def test_it_never_constructs_a_window(self):
        from apkpy_lib import ui
        from apkpy_lib.features import billing as preview
        if ui._app._instance is not None:
            self.skipTest("a Previewer window already exists in this process")
        preview.billing.buy("pro_unlock", on_result=lambda *_: None)
        preview.billing.prices(["pro_unlock"], on_result=lambda *_: None)
        self.assertIsNone(ui._app._instance)

    def test_prices_come_back_as_json_set_items_can_read(self):
        from apkpy_lib.features import billing as preview
        seen = []
        preview.billing.prices(["pro_unlock"], on_result=lambda ok, v: seen.append(v))
        row = json.loads(seen[0])[0]
        self.assertEqual(sorted(row), ["description", "id", "price", "title"])

    def test_the_pretend_price_says_so(self):
        from apkpy_lib.features import billing as preview
        seen = []
        preview.billing.prices(["x"], on_result=lambda ok, v: seen.append(v))
        self.assertIn("Previewer", json.loads(seen[0])[0]["description"])

    def test_a_subscription_price_differs_from_a_one_time_one(self):
        from apkpy_lib.features import billing as preview
        rows = []
        preview.billing.prices(["m"], kind="subscription",
                               on_result=lambda ok, v: rows.append(json.loads(v)))
        preview.billing.prices(["p"], on_result=lambda ok, v: rows.append(json.loads(v)))
        self.assertNotEqual(rows[0][0]["price"], rows[1][0]["price"])

    def test_owning_something_twice_is_refused_the_way_play_refuses_it(self):
        from apkpy_lib.features import billing as preview
        preview._owned["pro_unlock"] = {"id": "pro_unlock"}
        seen = []
        preview.billing.buy("pro_unlock", on_result=lambda ok, v: seen.append((ok, v)))
        self.assertEqual(seen, [(False, "owned")])

    def test_consuming_what_is_not_owned_says_so(self):
        from apkpy_lib.features import billing as preview
        seen = []
        preview.billing.consume("coins", on_result=lambda ok, v: seen.append((ok, v)))
        self.assertEqual(seen, [(False, "not_owned")])

    def test_the_pretend_token_cannot_be_mistaken_for_a_real_one(self):
        from apkpy_lib.features import billing as preview
        preview._owned["x"] = preview._row("x")
        seen = []
        preview.billing.owned(on_result=lambda ok, v: seen.append(v))
        self.assertIn("not-a-real-token", json.loads(seen[0])[0]["token"])


if __name__ == "__main__":
    unittest.main()
