# 1. Before you start

You need two things on your computer: Python and ApkPy. Run this to check them:

```bash
apkpy doctor
```

It looks at ApkPy, the Java and Android tools, and the game engine, and tells you what is missing and how to fix it.

## Two words you will see

- **The app** is the file `writehere.py`: ApkPy turns it into an Android app.
- **The game** is the file `game/main.py`, which the app opens.

## One rule

Your game file is **read, not run**. There is no Python on the phone: the build reads what you wrote and turns it into Java. So `game/main.py` is a description of your game, not a program that starts at the top and runs to the bottom.

If you write something the build cannot read, it stops and tells you the line and how to fix it.

Next: [2. Make the project](02-make-the-project.md)
