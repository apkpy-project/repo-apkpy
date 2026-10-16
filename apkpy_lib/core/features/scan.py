# -*- coding: utf-8 -*-
"""Compiler support for ``scan`` -- reading a barcode or a QR code.

    from apkpy_lib import button, scan

    def read(ok, value):
        if ok:
            result.set_value(value)

    button("Scan", id="scan", screen=home,
           command=lambda: scan.code(on_result=read))

**No camera permission.** This uses Google's own code scanner, which runs the
camera inside Play services rather than inside the app. The app never sees the
viewfinder, never holds the frames, and never has to ask for CAMERA -- which
also means one fewer permission on the store listing and one fewer thing for a
company's security review to argue about. The trade is a hard dependency on
Play services: an aged or Google-less device answers ``unavailable``.

**The contract is the usual one:** ``(ok, value)``. ``ok`` false comes with a
word, not a stack trace -- ``cancelled`` when the person backed out, which is
not an error and should not be shown as one, and ``unavailable`` when the
scanner cannot run on this device.
"""

# The symbologies worth naming. Restricting them is not decoration: a scanner
# told to read everything will happily read the wrong label off the same box,
# and a warehouse app that only ever wants a QR should say so.
FORMATS = {
    'qr': 'QR_CODE',
    'aztec': 'AZTEC',
    'data_matrix': 'DATA_MATRIX',
    'pdf417': 'PDF417',
    'code128': 'CODE_128',
    'code39': 'CODE_39',
    'code93': 'CODE_93',
    'codabar': 'CODABAR',
    'ean13': 'EAN_13',
    'ean8': 'EAN_8',
    'itf': 'ITF',
    'upc_a': 'UPC_A',
    'upc_e': 'UPC_E',
}

GRADLE = "com.google.android.gms:play-services-code-scanner:16.1.0"


def normalise_formats(names):
    """The Barcode constants for the names asked for, or () for every format.

    An unknown name is dropped rather than guessed at: reading the wrong
    symbology silently is worse than reading them all.
    """
    if not names:
        return ()
    chosen = []
    for name in names:
        constant = FORMATS.get(str(name).strip().lower())
        if constant and constant not in chosen:
            chosen.append(constant)
    return tuple(chosen)


def unknown_formats(names):
    """Names that mean nothing here, so the caller can say so out loud."""
    return [str(n) for n in (names or [])
            if str(n).strip().lower() not in FORMATS]


def uses_scan(tree):
    """Whether the module ever asks for a scan, read from the source."""
    import ast

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'scan'
                and node.func.attr == 'code'):
            return True
    return False


def activity_runtime_java(formats=()):
    """``_apkpyScanCode`` -- start the scanner and answer once.

    The three listeners are all registered on purpose. Without the cancel one
    a person who backs out of the scanner gets no callback at all, and the
    screen sits waiting for a value that is never coming.
    """
    if formats:
        first = formats[0]
        rest = ''.join(
            ',\n                        com.google.mlkit.vision.barcode.common.Barcode.FORMAT_%s'
            % name for name in formats[1:])
        options = (
            '        com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions options =\n'
            '                new com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions.Builder()\n'
            '                        .setBarcodeFormats(\n'
            '                                com.google.mlkit.vision.barcode.common.Barcode.FORMAT_%s%s)\n'
            '                        .build();\n'
            '        com.google.mlkit.vision.codescanner.GmsBarcodeScanner _scanner =\n'
            '                com.google.mlkit.vision.codescanner.GmsBarcodeScanning'
            '.getClient(this, options);\n' % (first, rest)
        )
    else:
        options = (
            '        com.google.mlkit.vision.codescanner.GmsBarcodeScanner _scanner =\n'
            '                com.google.mlkit.vision.codescanner.GmsBarcodeScanning'
            '.getClient(this);\n'
        )

    return '''
    /** scan.code(on_result=...) -- Google's scanner, in its own process. */
    private void _apkpyScanCode(final ApkpyScanCallback callback) {
%(options)s        _scanner.startScan()
                .addOnSuccessListener(barcode -> {
                    String value = barcode == null ? null : barcode.getRawValue();
                    // A shape the scanner found but could not read as text.
                    // Reporting success with "" would reach the app as an
                    // empty label that somebody had apparently scanned.
                    if (value == null) {
                        callback.onScan(false, "unreadable");
                    } else {
                        callback.onScan(true, value);
                    }
                })
                // Without this one, backing out of the scanner calls nothing
                // at all and the screen waits for a value never coming.
                .addOnCanceledListener(() -> callback.onScan(false, "cancelled"))
                .addOnFailureListener(problem -> callback.onScan(false, "unavailable"));
    }

    public interface ApkpyScanCallback {
        void onScan(boolean ok, String value);
    }
''' % {'options': options}
