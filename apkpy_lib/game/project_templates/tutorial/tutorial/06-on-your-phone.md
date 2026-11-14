# 6. On your phone

Connect your phone with a USB cable, with **USB debugging** turned on in the phone's developer options. Then:

```bash
apkpy run --usb
```

The first time takes a few minutes. Then the app is on your phone: open it, and press anywhere on the screen. The phone's Back button closes the game.

## Just the APK

To get the file without installing it:

```bash
apkpy run
```

The APK appears in your project folder. You can send it to a phone and install it there.

## If something goes wrong

Run this, and follow what it says:

```bash
apkpy doctor
```

Next: [7. Try changing things](07-try-changing-things.md)
