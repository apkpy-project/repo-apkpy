"""Compiler support for ``billing`` -- Google Play in-app purchases.

Selling something inside the app: a one-time unlock, a pack of coins, or a
subscription.

    billing.prices(["pro_unlock", "coins_100"], on_result=shown)
    billing.buy("pro_unlock", on_result=bought)
    billing.buy("coins_100", consumable=True, on_result=bought)

    billing.prices(["monthly"], kind="subscription", on_result=shown)
    billing.subscribe("monthly", on_result=bought)

    billing.owned(on_result=restored)

**The library acknowledges every purchase for you, and that is not a
convenience.** Google refunds any purchase an app fails to acknowledge within
three days: forget it and the money goes back, the person keeps nothing, and
nobody tells you. A consumable is consumed instead, which is what lets it be
bought again. Getting this wrong is the single most expensive mistake in Play
billing, so the choice here is one keyword rather than a call you can omit.

**Prices are never hardcoded.** ``prices()`` asks Play, which answers in the
person's own currency, already formatted for their locale. A price written into
the app is wrong in most of the world and illegal in some of it.

**On-device ownership is a hint, not proof.** Everything ``owned()`` returns
carries a ``token``; anything worth money should be checked server-side against
the Play Developer API with that token. A rooted phone can lie to this API and
the app cannot tell.
"""

from __future__ import annotations

import ast

__all__ = [
    "COMMAND_TYPES", "REASONS", "PERMISSION", "GRADLE_DEPENDENCY", "SUCCESS",
    "PRODUCT_KINDS", "normalise_kind",
    "is_call", "parse_call", "commands_use_billing", "emit_command",
    "callback_interface_java", "activity_runtime_java", "shared_class_java",
]


COMMAND_TYPES = frozenset({
    "billing_prices", "billing_buy", "billing_owned", "billing_consume",
})

SUCCESS = "ok"

PERMISSION = "com.android.vending.BILLING"
GRADLE_DEPENDENCY = "com.android.billingclient:billing:7.1.1"

PRODUCT_KINDS = {
    "product": "inapp", "inapp": "inapp", "one-time": "inapp", "onetime": "inapp",
    "subscription": "subs", "subs": "subs", "sub": "subs",
}


def normalise_kind(value):
    """``"subscription"`` or ``"product"`` -> what Play calls it."""
    if value is None:
        return "inapp"
    return PRODUCT_KINDS.get(str(value).strip().lower(), "inapp")


REASONS = {
    "ok": "It worked.",
    "cancelled": "The person backed out of the payment sheet.",
    "owned": "They already own this. Nothing was charged.",
    "pending": "Payment started but has not cleared -- cash or a slow method. "
               "Do not deliver anything yet.",
    "not_found": "No product with that id. Check the id in Play Console, and "
                 "that the app is published to a track.",
    "not_supported": "This device has no Play Store, or billing is not "
                     "available on it.",
    "unavailable": "Play's billing service could not be reached.",
    "network": "The network failed during the purchase.",
    "denied": "Play refused the call. Usually an unsigned build, an app that "
              "is not on a track, or an account that is not a licensed tester.",
    "not_owned": "Nothing to consume or acknowledge: they do not own it.",
    "failed": "It did not work, for another reason.",
}

# BillingClient.BillingResponseCode -> our vocabulary. The generated switch is
# emitted from this table, so the two sides cannot drift.
_RESPONSE_CODES = {
    0: "ok",                 # OK
    1: "cancelled",          # USER_CANCELED
    2: "unavailable",        # SERVICE_UNAVAILABLE
    3: "not_supported",      # BILLING_UNAVAILABLE
    4: "not_found",          # ITEM_UNAVAILABLE
    5: "denied",             # DEVELOPER_ERROR
    6: "failed",             # ERROR
    7: "owned",              # ITEM_ALREADY_OWNED
    8: "not_owned",          # ITEM_NOT_OWNED
    12: "network",           # NETWORK_ERROR
    -1: "unavailable",       # SERVICE_DISCONNECTED
    -2: "not_supported",     # FEATURE_NOT_SUPPORTED
    -3: "unavailable",       # SERVICE_TIMEOUT
}


def reason_for_code(code):
    return _RESPONSE_CODES.get(int(code), "failed")


# --- Parsing ---------------------------------------------------------------

def is_call(call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "billing"
        and func.attr in ("prices", "buy", "subscribe", "owned", "consume")
    )


def _literal(transpiler, node, default=None):
    if node is None:
        return default
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        found = getattr(transpiler, "string_constants", {}).get(node.id)
        return default if found is None else found
    return default


def _ids(transpiler, call):
    """The product ids, which have to be known at compile time.

    They end up in the APK and in Play Console; a runtime value could not be
    checked against either, so a non-literal is dropped rather than guessed.
    """
    node = call.args[0] if call.args else transpiler._kw_node(call.keywords, "ids")
    if node is None:
        node = transpiler._kw_node(call.keywords, "products")
    values = []
    if isinstance(node, ast.Constant):
        values = [str(node.value)]
    elif isinstance(node, (ast.List, ast.Tuple)):
        for item in node.elts:
            if isinstance(item, ast.Constant):
                values.append(str(item.value))
    elif isinstance(node, ast.Name):
        listed = getattr(transpiler, "list_assignments", {}).get(node.id)
        if listed is not None:
            for item in listed.elts:
                if isinstance(item, ast.Constant):
                    values.append(str(item.value))
        else:
            found = getattr(transpiler, "string_constants", {}).get(node.id)
            if found is not None:
                values.append(str(found))
    return values


def parse_call(transpiler, call):
    verb = call.func.attr
    if PERMISSION not in transpiler.declared_permissions:
        transpiler.declared_permissions.append(PERMISSION)

    command = {"type": "billing_" + ("buy" if verb == "subscribe" else verb)}

    callback = transpiler._kw(call.keywords, "on_result")
    if callback:
        transpiler.boolean_first_arg_callbacks.add(callback)
        command["callback"] = callback

    if verb == "prices":
        command["ids"] = _ids(transpiler, call)
        command["kind"] = normalise_kind(
            _literal(transpiler, transpiler._kw_node(call.keywords, "kind")))
    elif verb in ("buy", "subscribe"):
        ids = _ids(transpiler, call)
        command["product"] = ids[0] if ids else ""
        # subscribe() is buy() with the kind decided, so an app cannot pass a
        # subscription id to the one-time flow by accident.
        command["kind"] = "subs" if verb == "subscribe" else normalise_kind(
            _literal(transpiler, transpiler._kw_node(call.keywords, "kind")))
        command["consumable"] = bool(_literal(
            transpiler, transpiler._kw_node(call.keywords, "consumable"), False))
    elif verb == "consume":
        ids = _ids(transpiler, call)
        command["product"] = ids[0] if ids else ""

    return command


def commands_use_billing(functions_map, module_init_cmds=None):
    def _uses(cmds):
        return any((cmd.get("type") in COMMAND_TYPES) for cmd in (cmds or []))

    if _uses(module_init_cmds):
        return True
    return any(info and _uses(info.get("cmds", []))
               for info in (functions_map or {}).values())


# --- Emission --------------------------------------------------------------

def _java_string(value):
    text = "" if value is None else str(value)
    return '"%s"' % (
        text.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    )


def _java_array(values):
    if not values:
        return "new String[0]"
    return "new String[]{%s}" % ", ".join(_java_string(v) for v in values)


def emit_command(lines, indent, command, val_to_java=None, functions_map=None):
    kind = command.get("type")
    callback = command.get("callback")
    handler = ("(success, value) -> pythonCallback_%s(success, value)" % callback
               if callback else "null")

    if kind == "billing_prices":
        lines.append("%s_billingPrices(%s, %s, %s);" % (
            indent, _java_array(command.get("ids")),
            _java_string(command.get("kind", "inapp")), handler))
    elif kind == "billing_buy":
        lines.append("%s_billingBuy(%s, %s, %s, %s);" % (
            indent, _java_string(command.get("product")),
            _java_string(command.get("kind", "inapp")),
            "true" if command.get("consumable") else "false", handler))
    elif kind == "billing_owned":
        lines.append("%s_billingOwned(%s);" % (indent, handler))
    elif kind == "billing_consume":
        lines.append("%s_billingConsume(%s, %s);" % (
            indent, _java_string(command.get("product")), handler))


def callback_interface_java(package):
    return ("    private interface BillingResultCallback "
            "extends " + package + ".ApkpyBilling.Listener { }")


def activity_runtime_java(package):
    """Thin calls: the store connection itself belongs to the app."""
    return '''
    // The billing client lives in ApkpyBilling so one connection serves every
    // screen. Only launching the payment sheet needs an Activity.

    private void _billingPrices(String[] ids, String kind,
                                BillingResultCallback cb) {
        %(package)s.ApkpyBilling.prices(this, ids, kind, cb);
    }

    private void _billingBuy(String product, String kind, boolean consumable,
                             BillingResultCallback cb) {
        %(package)s.ApkpyBilling.buy(this, product, kind, consumable, cb);
    }

    private void _billingOwned(BillingResultCallback cb) {
        %(package)s.ApkpyBilling.owned(this, cb);
    }

    private void _billingConsume(String product, BillingResultCallback cb) {
        %(package)s.ApkpyBilling.consume(this, product, cb);
    }
''' % {"package": package}


def shared_class_java(package):
    """One connection to Play for the whole app, and the acknowledge rule."""
    arms = "\n".join(
        '            case %d: return "%s";' % (code, reason)
        for code, reason in sorted(_RESPONSE_CODES.items())
    )
    return '''package %(package)s;

public final class ApkpyBilling {

    public interface Listener { void onResult(boolean ok, String value); }

    private static final android.os.Handler MAIN =
            new android.os.Handler(android.os.Looper.getMainLooper());

    // Touched from binder threads and from the main one.
    private static volatile com.android.billingclient.api.BillingClient sClient;
    private static final java.util.HashMap<String,
            com.android.billingclient.api.ProductDetails> DETAILS =
                    new java.util.HashMap<>();

    // The purchase sheet answers through a listener on the client, not through
    // the call that opened it, so the caller is remembered here.
    private static volatile Listener sPending;
    private static volatile boolean sPendingConsumable;

    private ApkpyBilling() { }

    private static void post(final Listener cb, final boolean ok, final String value) {
        if (cb == null) return;
        MAIN.post(new Runnable() {
            @Override public void run() { cb.onResult(ok, value); }
        });
    }

    public static String reasonFor(int code) {
        switch (code) {
%(arms)s
            default: return "failed";
        }
    }

    private static String jsonEscape(String raw) {
        if (raw == null) return "";
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (c == '"' || c == '\\\\') out.append('\\\\').append(c);
            else if (c >= ' ') out.append(c);
        }
        return out.toString();
    }

    /** Run something with a connected client, or report why we cannot. */
    private static void withClient(final android.content.Context ctx,
                                   final Runnable then, final Listener cb) {
        if (sClient != null && sClient.isReady()) { then.run(); return; }
        // Replacing a live-but-unready client without ending it leaves a
        // service binding behind on every retry.
        try { if (sClient != null) sClient.endConnection(); } catch (Exception ignored) { }
        sClient = com.android.billingclient.api.BillingClient
                .newBuilder(ctx.getApplicationContext())
                .enablePendingPurchases(
                        com.android.billingclient.api.PendingPurchasesParams
                                .newBuilder().enableOneTimeProducts().build())
                .setListener(new com.android.billingclient.api.PurchasesUpdatedListener() {
                    @Override
                    public void onPurchasesUpdated(
                            com.android.billingclient.api.BillingResult result,
                            java.util.List<com.android.billingclient.api.Purchase> purchases) {
                        Listener waiting = sPending;
                        sPending = null;
                        int code = result.getResponseCode();
                        if (code != 0) { post(waiting, false, reasonFor(code)); return; }
                        if (purchases == null || purchases.isEmpty()) {
                            post(waiting, false, "failed");
                            return;
                        }
                        // Play can hand back more than one purchase in a
                        // single update. Telling the caller once per row would
                        // fire its callback several times for one tap, so only
                        // the first reports and the rest are just settled.
                        boolean first = true;
                        for (com.android.billingclient.api.Purchase p : purchases) {
                            settle(p, sPendingConsumable, first ? waiting : null);
                            first = false;
                        }
                    }
                })
                .build();
        sClient.startConnection(
                new com.android.billingclient.api.BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(
                    com.android.billingclient.api.BillingResult result) {
                if (result.getResponseCode() == 0) then.run();
                else post(cb, false, reasonFor(result.getResponseCode()));
            }

            @Override
            public void onBillingServiceDisconnected() {
                // Left for the next call to reconnect: retrying here would
                // loop against a Play Store that is updating.
            }
        });
    }

    /**
     * Acknowledge or consume, then report.
     *
     * Google refunds any purchase an app has not acknowledged within three
     * days. Doing it here rather than leaving it to the caller is the whole
     * reason this class exists.
     */
    private static void settle(final com.android.billingclient.api.Purchase purchase,
                               final boolean consumable, final Listener cb) {
        if (purchase.getPurchaseState()
                == com.android.billingclient.api.Purchase.PurchaseState.PENDING) {
            // Cash or a slow method: nothing is owed yet, and nothing should
            // be unlocked.
            post(cb, false, "pending");
            return;
        }
        if (purchase.getPurchaseState()
                != com.android.billingclient.api.Purchase.PurchaseState.PURCHASED) {
            post(cb, false, "failed");
            return;
        }
        final String json = describe(purchase);
        if (consumable) {
            sClient.consumeAsync(
                    com.android.billingclient.api.ConsumeParams.newBuilder()
                            .setPurchaseToken(purchase.getPurchaseToken()).build(),
                    new com.android.billingclient.api.ConsumeResponseListener() {
                        @Override
                        public void onConsumeResponse(
                                com.android.billingclient.api.BillingResult result,
                                String token) {
                            if (result.getResponseCode() == 0) post(cb, true, json);
                            else post(cb, false, reasonFor(result.getResponseCode()));
                        }
                    });
        } else if (!purchase.isAcknowledged()) {
            sClient.acknowledgePurchase(
                    com.android.billingclient.api.AcknowledgePurchaseParams.newBuilder()
                            .setPurchaseToken(purchase.getPurchaseToken()).build(),
                    new com.android.billingclient.api.AcknowledgePurchaseResponseListener() {
                        @Override
                        public void onAcknowledgePurchaseResponse(
                                com.android.billingclient.api.BillingResult result) {
                            if (result.getResponseCode() == 0) post(cb, true, json);
                            else post(cb, false, reasonFor(result.getResponseCode()));
                        }
                    });
        } else {
            post(cb, true, json);
        }
    }

    private static String describe(com.android.billingclient.api.Purchase purchase) {
        StringBuilder json = new StringBuilder("{");
        String id = purchase.getProducts().isEmpty()
                ? "" : purchase.getProducts().get(0);
        json.append("\\"id\\":\\"").append(jsonEscape(id)).append("\\"");
        // The token is what a server checks against the Play Developer API.
        // On-device state can be faked; this is what cannot.
        json.append(",\\"token\\":\\"")
            .append(jsonEscape(purchase.getPurchaseToken())).append("\\"");
        json.append(",\\"order\\":\\"")
            .append(jsonEscape(purchase.getOrderId())).append("\\"");
        json.append(",\\"time\\":\\"")
            .append(purchase.getPurchaseTime()).append("\\"");
        json.append("}");
        return json.toString();
    }

    public static void prices(final android.content.Context ctx,
                              final String[] ids, final String kind,
                              final Listener cb) {
        if (ids == null || ids.length == 0) { post(cb, false, "not_found"); return; }
        withClient(ctx, new Runnable() {
            @Override public void run() {
                java.util.ArrayList<com.android.billingclient.api.QueryProductDetailsParams.Product>
                        wanted = new java.util.ArrayList<>();
                for (String id : ids) {
                    wanted.add(com.android.billingclient.api.QueryProductDetailsParams.Product
                            .newBuilder().setProductId(id).setProductType(kind).build());
                }
                sClient.queryProductDetailsAsync(
                        com.android.billingclient.api.QueryProductDetailsParams.newBuilder()
                                .setProductList(wanted).build(),
                        new com.android.billingclient.api.ProductDetailsResponseListener() {
                            @Override
                            public void onProductDetailsResponse(
                                    com.android.billingclient.api.BillingResult result,
                                    java.util.List<com.android.billingclient.api.ProductDetails> list) {
                                if (result.getResponseCode() != 0) {
                                    post(cb, false, reasonFor(result.getResponseCode()));
                                    return;
                                }
                                if (list == null || list.isEmpty()) {
                                    post(cb, false, "not_found");
                                    return;
                                }
                                StringBuilder json = new StringBuilder("[");
                                boolean first = true;
                                for (com.android.billingclient.api.ProductDetails d : list) {
                                    DETAILS.put(d.getProductId(), d);
                                    if (!first) json.append(",");
                                    first = false;
                                    json.append("{\\"id\\":\\"")
                                        .append(jsonEscape(d.getProductId()))
                                        .append("\\",\\"title\\":\\"")
                                        .append(jsonEscape(d.getTitle()))
                                        .append("\\",\\"description\\":\\"")
                                        .append(jsonEscape(d.getDescription()))
                                        .append("\\",\\"price\\":\\"")
                                        .append(jsonEscape(priceOf(d)))
                                        .append("\\"}");
                                }
                                json.append("]");
                                post(cb, true, json.toString());
                            }
                        });
            }
        }, cb);
    }

    /** The formatted price, in the person's own currency. */
    private static String priceOf(com.android.billingclient.api.ProductDetails d) {
        try {
            if (d.getOneTimePurchaseOfferDetails() != null) {
                return d.getOneTimePurchaseOfferDetails().getFormattedPrice();
            }
            java.util.List<com.android.billingclient.api.ProductDetails.SubscriptionOfferDetails>
                    offers = d.getSubscriptionOfferDetails();
            if (offers != null && !offers.isEmpty()) {
                // The first offer is the one buy() launches, so it is the one
                // whose price the app should be showing.
                return offers.get(0).getPricingPhases().getPricingPhaseList()
                        .get(0).getFormattedPrice();
            }
        } catch (Exception ignored) { }
        return "";
    }

    public static void buy(final android.app.Activity activity, final String product,
                           final String kind, final boolean consumable,
                           final Listener cb) {
        withClient(activity, new Runnable() {
            @Override public void run() {
                com.android.billingclient.api.ProductDetails details =
                        DETAILS.get(product);
                if (details == null) {
                    // Prices were never asked for, so Play has told us nothing
                    // about this id yet. Ask, then come back.
                    prices(activity, new String[]{product}, kind, new Listener() {
                        @Override public void onResult(boolean ok, String value) {
                            if (!ok) { post(cb, false, value); return; }
                            MAIN.post(new Runnable() {
                                @Override public void run() {
                                    launch(activity, product, consumable, cb);
                                }
                            });
                        }
                    });
                    return;
                }
                launch(activity, product, consumable, cb);
            }
        }, cb);
    }

    private static void launch(android.app.Activity activity, String product,
                               boolean consumable, Listener cb) {
        com.android.billingclient.api.ProductDetails details = DETAILS.get(product);
        if (details == null) { post(cb, false, "not_found"); return; }
        com.android.billingclient.api.BillingFlowParams.ProductDetailsParams.Builder one =
                com.android.billingclient.api.BillingFlowParams.ProductDetailsParams
                        .newBuilder().setProductDetails(details);
        try {
            java.util.List<com.android.billingclient.api.ProductDetails.SubscriptionOfferDetails>
                    offers = details.getSubscriptionOfferDetails();
            if (offers != null && !offers.isEmpty()) {
                // A subscription cannot be launched without naming an offer.
                one.setOfferToken(offers.get(0).getOfferToken());
            }
        } catch (Exception ignored) { }
        sPending = cb;
        sPendingConsumable = consumable;
        com.android.billingclient.api.BillingResult result = sClient.launchBillingFlow(
                activity,
                com.android.billingclient.api.BillingFlowParams.newBuilder()
                        .setProductDetailsParamsList(
                                java.util.Collections.singletonList(one.build()))
                        .build());
        if (result.getResponseCode() != 0) {
            sPending = null;
            post(cb, false, reasonFor(result.getResponseCode()));
        }
    }

    public static void owned(final android.content.Context ctx, final Listener cb) {
        withClient(ctx, new Runnable() {
            @Override public void run() {
                final StringBuilder json = new StringBuilder("[");
                collect(ctx, "inapp", json, new Runnable() {
                    @Override public void run() {
                        collect(ctx, "subs", json, new Runnable() {
                            @Override public void run() {
                                json.append("]");
                                post(cb, true, json.toString());
                            }
                        }, cb);
                    }
                }, cb);
            }
        }, cb);
    }

    private static void collect(android.content.Context ctx, String kind,
                                final StringBuilder json, final Runnable then,
                                final Listener cb) {
        sClient.queryPurchasesAsync(
                com.android.billingclient.api.QueryPurchasesParams.newBuilder()
                        .setProductType(kind).build(),
                new com.android.billingclient.api.PurchasesResponseListener() {
                    @Override
                    public void onQueryPurchasesResponse(
                            com.android.billingclient.api.BillingResult result,
                            java.util.List<com.android.billingclient.api.Purchase> purchases) {
                        if (result.getResponseCode() != 0) {
                            post(cb, false, reasonFor(result.getResponseCode()));
                            return;
                        }
                        if (purchases != null) {
                            for (com.android.billingclient.api.Purchase p : purchases) {
                                if (p.getPurchaseState()
                                        != com.android.billingclient.api.Purchase
                                                .PurchaseState.PURCHASED) {
                                    continue;
                                }
                                if (json.length() > 1) json.append(",");
                                json.append(describe(p));
                                // A purchase that completed while the app was
                                // closed never reaches onPurchasesUpdated, so
                                // this is the only place it can be settled.
                                // Without it Google refunds it after three
                                // days -- the very thing this class exists to
                                // prevent, missed in the one case where the
                                // app was not watching.
                                rescue(p);
                            }
                        }
                        then.run();
                    }
                });
    }

    /** Acknowledge something bought while nobody was looking. */
    private static void rescue(com.android.billingclient.api.Purchase purchase) {
        if (purchase.isAcknowledged()) return;
        try {
            sClient.acknowledgePurchase(
                    com.android.billingclient.api.AcknowledgePurchaseParams.newBuilder()
                            .setPurchaseToken(purchase.getPurchaseToken()).build(),
                    new com.android.billingclient.api.AcknowledgePurchaseResponseListener() {
                        @Override
                        public void onAcknowledgePurchaseResponse(
                                com.android.billingclient.api.BillingResult result) {
                            // Nothing to report: the app already has the row.
                            // Acknowledging a consumable is harmless -- it can
                            // still be consumed afterwards.
                        }
                    });
        } catch (Exception ignored) { }
    }

    public static void consume(final android.content.Context ctx,
                               final String product, final Listener cb) {
        withClient(ctx, new Runnable() {
            @Override public void run() {
                sClient.queryPurchasesAsync(
                        com.android.billingclient.api.QueryPurchasesParams.newBuilder()
                                .setProductType("inapp").build(),
                        new com.android.billingclient.api.PurchasesResponseListener() {
                            @Override
                            public void onQueryPurchasesResponse(
                                    com.android.billingclient.api.BillingResult result,
                                    java.util.List<com.android.billingclient.api.Purchase> purchases) {
                                if (result.getResponseCode() != 0) {
                                    post(cb, false, reasonFor(result.getResponseCode()));
                                    return;
                                }
                                if (purchases != null) {
                                    for (com.android.billingclient.api.Purchase p : purchases) {
                                        if (p.getProducts().contains(product)) {
                                            settle(p, true, cb);
                                            return;
                                        }
                                    }
                                }
                                post(cb, false, "not_owned");
                            }
                        });
            }
        }, cb);
    }
}
''' % {"package": package, "arms": arms}
