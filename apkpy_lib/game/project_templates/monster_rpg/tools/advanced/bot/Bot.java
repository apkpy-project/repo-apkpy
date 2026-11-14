package apkpygame.game;

import apkpygame.core.Entity;
import apkpygame.core.Game;
import apkpygame.core.Platform;
import apkpygame.core.components.ScrollList;
import apkpygame.testkit.HeadlessPlatform;

import java.io.File;
import java.nio.file.Files;

/**
 * Plays the start of the game the way a person would: only keys and taps, reading the game's state to
 * decide. It goes through every feature, then writes what it did as a replay (the same game on any device).
 * Run it with tools/play_bot.py. When you change the game's opening, change the plan in play().
 */
public final class Bot {
    final HeadlessPlatform platform;
    Game game;
    final StringBuilder replay = new StringBuilder();
    long step;
    int battles, captures, evolved;
    final java.util.Set<String> tried = new java.util.TreeSet<String>();

    Bot(HeadlessPlatform platform) {
        this.platform = platform;
    }

    static RuntimeException stuck(String why) {
        return new IllegalStateException("the bot is stuck: " + why);
    }

    // ── hands ────────────────────────────────────────────────────────────

    void mark(String feature) {
        tried.add(feature);
        System.out.println(step + " " + feature);
    }

    void note(String event) {
        if (replay.length() > 0) replay.append(',');
        replay.append(event);
    }

    String describe() {
        M_state__store.class.getName();
        String battle = "";
        Entity ui = game.scene().find("battle_ui");
        if (ui != null) {
            battle = " battle: must_switch=" + M_state__store.BATTLE.must_switch + " over=" + M_state__store.BATTLE.over
                    + " lines=" + M_state__store.BATTLE.lines.size() + " listVisible=" + ui.get(ScrollList.class).visible
                    + " listCount=" + ui.get(ScrollList.class).count + " fight=" + ui.child("fight").active
                    + " m0=" + ui.child("m0").active + " back=" + ui.child("back").active;
            for (Monster m : M_state__store.SESSION.save.team) battle += " [" + m.species + " L" + m.level + " hp" + m.hp + "]";
        }
        return "in " + scene() + " run=" + M_state__store.RUN.active + "/" + M_state__store.RUN.event + " say='" + M_state__store.UI.say
                + "' screen=" + M_state__store.UI.screen + battle;
    }

    /** While true, the controls must stay on the screen at every step (walking over a trigger that has nothing to say). */
    boolean watchControls;

    void tick() {
        if (watchControls && scene().equals("village") && !game.scene().find("pad").active) {
            throw stuck("the controls went away at " + col() + "," + row());
        }
        if (game.isEnded()) throw stuck("the game ended: " + game.endJson());
        if (step > 200000) throw stuck(describe());
        game.step();
        step++;
    }

    void ticks(int n) {
        for (int i = 0; i < n; i++) keepGoing();
    }

    /** One step; a battle or a dialog that comes up is dealt with before going on. */
    void keepGoing() {
        tick();
    }

    void tap(double x, double y) {
        note(step + ":tap:" + (int) x + ":" + (int) y);
        game.input.pointerDown(0, x, y);
        tick();
        game.input.pointerUp(0, x, y);
        tick();
        ticks(2);
    }

    void key(String name, boolean down) {
        note(step + ":" + name + ":" + (down ? "down" : "up"));
        if (down) game.input.keyDown(name);
        else game.input.keyUp(name);
    }

    void back() {
        note(step + ":back:down");
        game.back();
    }

    String scene() {
        return game.scene().name;
    }

    Entity hero() {
        return game.scene().find("hero");
    }

    int col() {
        return (int) Math.floor(hero().transform.x / 16);
    }

    int row() {
        return (int) Math.floor(hero().transform.y / 16);
    }

    boolean busy() {
        return M_state__store.RUN.active || !M_state__store.UI.say.isEmpty() || !M_state__store.UI.screen.isEmpty();
    }

    // ── dialogs and battles ──────────────────────────────────────────────

    /** Taps through what is being said, until the world is free again. Battles on the way are fought. */
    void settle() {
        for (int i = 0; i < 40000; i++) {
            if (scene().equals("battle")) {
                fightBattle();
                continue;
            }
            if (!M_state__store.UI.screen.isEmpty()) return;
            if (!M_state__store.UI.say.isEmpty()) {
                if (M_state__store.UI.asking) {
                    ticks(120);
                    return;
                }
                tap(240, 60);
                ticks(4);
                continue;
            }
            if (!busy()) {
                ticks(8);
                if (!busy() && !scene().equals("battle")) return;
            } else {
                tick();
            }
        }
        throw stuck("never settled, in " + scene() + ", event " + M_state__store.RUN.event + " at " + M_state__store.RUN.at);
    }

    void fightBattle() {
        battles++;
        for (int i = 0; i < 60000 && scene().equals("battle"); i++) {
            Entity ui = game.scene().find("battle_ui");
            if (ui == null) {
                tick();
                continue;
            }
            if (ui.child("fight").active) {
                chooseAction(ui);
            } else if (ui.get(ScrollList.class).visible && M_state__store.BATTLE.must_switch) {
                tap(361, 116 + 15 + M_battle__engine.first_able() * 32);      // the list opened for a forced switch
                ticks(30);
            } else {
                tick();
                if (step % 20 == 0) tapTop();
            }
        }
    }

    void tapTop() {
        tap(240, 60);
    }

    void chooseAction(Entity ui) {
        ticks(10);
        M_battle__engine.class.getName();
        apkpygame.game.Monster foe = M_battle__engine.foe();
        double left = foe.hp * 1.0 / M_rules__monsters.max_hp(foe);
        boolean wild = M_state__store.BATTLE.wild;
        int knots = M_state__store.SESSION.save.bag.containsKey("bond_knot") ? M_state__store.SESSION.save.bag.get("bond_knot") : 0;
        if (wild && knots > 0 && left < 0.75 && M_state__store.SESSION.save.caught.size() < 3) {
            tap(418, 210);                               // Bag
            ticks(10);
            tryBagRow(ui);
            captures++;
            mark("knot");
            ticks(30);
            return;
        }
        tap(304, 210);                                   // Fight
        ticks(10);
        apkpygame.game.Monster me = M_battle__engine.ally();
        int move = 0;
        for (int i = 0; i < me.moves.size(); i++) {
            if (M_data__defs.MOVES.get(me.moves.get(i).move).power > 0 && me.moves.get(i).pp > 0) {
                move = i;
                if (i > 0) break;
            }
        }
        tap(move % 2 == 0 ? 304 : 418, move < 2 ? 210 : 248);
        ticks(30);
    }

    void tryBagRow(Entity ui) {
        // the list shows the usable items; the bot looks for the knot's row
        int row = 0, i = 0;
        for (String k : M_state__store.SESSION.save.bag.keySet()) {
            if (M_data__defs.ITEMS.get(k).kind.equals("key")) continue;
            if (k.equals("bond_knot")) row = i;
            i++;
        }
        tap(361, 116 + 15 + row * 32);
    }

    // ── walking ──────────────────────────────────────────────────────────

    /** Walks to a cell of this map, straight lines, x first or y first as said. A warp to another map ends it. */
    void walkTo(int c, int r, boolean xFirst) {
        String where = scene();
        if (xFirst) {
            line(c, row());
            if (scene().equals(where)) line(c, r);
        } else {
            line(col(), r);
            if (scene().equals(where)) line(c, r);
        }
    }

    void line(int c, int r) {
        String where = scene();
        for (int guard = 0; guard < 80; guard++) {
            settle();
            if (!scene().equals(where) || hero() == null) return;
            int dx = c - col(), dy = r - row();
            if (dx == 0 && dy == 0) return;
            String k = dx > 0 ? "right" : dx < 0 ? "left" : dy > 0 ? "down" : "up";
            key(k, true);
            int before = col() * 1000 + row();
            for (int i = 0; i < 60 && col() * 1000 + row() == before && !busy() && scene().equals(where); i++) tick();
            key(k, false);
            ticks(14);
        }
        throw stuck("cannot reach " + c + "," + r + " in " + where + " from " + col() + "," + row());
    }

    void face(String k) {
        settle();
        key(k, true);
        ticks(3);
        key(k, false);
        ticks(8);
    }

    /** Holds a direction for a moment, against something (a door). */
    void push(String k) {
        settle();
        key(k, true);
        ticks(4);
        key(k, false);
        ticks(4);
    }

    void pressA() {
        key("space", true);
        tick();
        key("space", false);
        ticks(3);
    }

    /** The menu button, then one of the menu's buttons. */
    void openFromMenu(double y) {
        settle();
        tap(418, 30);
        ticks(6);
        tap(240, y);
        ticks(6);
    }

    void closeScreen() {
        tap(430, 235);
        ticks(6);
    }

    // ── the plan ─────────────────────────────────────────────────────────

    void play() {
        game = Game.load(platform);
        game.start("title", "{}");
        game.viewport.update((int) game.config.width, (int) game.config.height);
        ticks(10);
        tap(240, 150);                                    // anywhere on the title: here, where New journey will appear
        ticks(10);
        if (game.scene().find("name_page").active) throw stuck("the tap on the title also pressed New journey");
        tap(240, 150);                                    // New journey
        ticks(10);
        tap(96, 131);                                     // A
        tap(114, 84);                                     // a letter of the top row
        tap(386, 226);                                    // OK
        ticks(90);
        if (!scene().equals("village")) throw stuck("no village: " + scene());
        settle();
        mark("title, name");

        walkTo(7, 12, true);                              // the villager: a gift
        face("up");
        pressA();
        settle();
        if (!M_state__store.SESSION.save.bag.containsKey("bond_knot")) throw stuck("no knots from the villager");
        mark("talk, give_item");

        walkTo(10, 2, true);                              // the gate turns you back: no partner yet
        for (int again = 0; again < 2; again++) {
            key("up", true);
            for (int i = 0; i < 40 && row() == 2; i++) tick();
            key("up", false);
            ticks(14);
            settle();
            if (row() != 2) throw stuck("the gate let the hero through: " + col() + "," + row());
        }
        int atCol = col(), atRow = row();
        tap(240, 60);                                     // tapping the map does not walk
        ticks(60);
        if (col() != atCol || row() != atRow) throw stuck("a tap on the map moved the hero");
        mark("trigger, step_back");

        walkTo(5, 6, false);                              // the Keeper
        walkTo(5, 5, true);
        ticks(30);
        if (!scene().equals("village")) throw stuck("next to the door, it opened by itself");
        push("up");                                       // a door opens by walking against it
        ticks(70);
        mark("door");
        if (!scene().equals("house")) throw stuck("no house: " + scene());
        walkTo(4, 5, true);
        walkTo(4, 3, false);
        face("up");
        pressA();
        settle();
        if (!M_state__store.UI.screen.equals("starter")) throw stuck("no starter screen");
        ticks(10);
        tap(105, 145);                                    // the first partner: only its page
        ticks(10);
        if (!M_state__store.SESSION.save.team.isEmpty()) throw stuck("tapping a partner took it at once");
        if (!game.scene().find("screen").child("page").active) throw stuck("no page about the partner");
        mark("partner's page");
        tap(130, 207);                                    // look at another
        ticks(10);
        if (game.scene().find("screen").child("page").active) throw stuck("looking at another did not go back");
        tap(105, 145);
        ticks(10);
        tap(270, 207);                                    // take it
        ticks(10);
        settle();
        if (M_state__store.SESSION.save.team.isEmpty()) throw stuck("no partner");
        mark("starter screen");
        face("up");
        pressA();
        for (int i = 0; i < 200 && !M_state__store.UI.asking; i++) tick();
        ticks(140);
        tap(385, 169);                                    // Yes (over the dialog box)
        ticks(10);
        settle();
        mark("ask");

        walkTo(4, 5, false);                              // out
        push("down");
        ticks(70);
        if (!scene().equals("village")) throw stuck("still inside");
        walkTo(14, 7, false);                             // the stall
        face("right");
        pressA();
        settle();
        if (!M_state__store.UI.screen.equals("shop")) throw stuck("no shop");
        ticks(10);
        int shells = M_state__store.SESSION.save.money;
        tap(130, 61);                                     // a Tonic: only its description
        ticks(6);
        if (M_state__store.SESSION.save.money != shells) throw stuck("tapping an item bought it");
        tap(305, 210);                                    // Buy
        ticks(6);
        if (M_state__store.SESSION.save.money != shells - 100) throw stuck("the Buy button did not buy");
        tap(130, 61 + 34 * 3);                            // and a knot
        ticks(6);
        tap(305, 210);
        mark("buy");
        mark("shop");
        closeScreen();
        settle();

        openFromMenu(135 - 90);                           // Team
        mark("team");
        closeScreen();
        openFromMenu(135 - 56);                           // Bag
        tap(130, 61);
        mark("bag");
        closeScreen();
        openFromMenu(135 - 22);                           // Encyclopedia
        tap(54, 55);
        note(step + ":drag:130:220:130:80:10");
        drag(130, 220, 130, 80, 10);
        mark("encyclopedia, scrolling");
        closeScreen();
        openFromMenu(135 + 46);                           // Options
        tap(170, 65);                                     // music off
        tap(170, 65);                                     // and on
        tap(240, 123);                                    // a sound volume
        mark("options");
        tap(300, 220);
        ticks(6);
        openFromMenu(135 + 12);                           // Save
        tap(200, 160);
        mark("save");
        tap(300, 160);
        ticks(6);
        back();                                           // Back opens the menu, and closes it
        ticks(6);
        if (!M_state__store.UI.screen.equals("menu")) throw stuck("Back did not open the menu");
        back();
        ticks(6);
        mark("back");

        walkTo(10, 7, true);                              // north, over the gate: it has nothing to say now
        watchControls = true;
        walkTo(10, 1, false);
        watchControls = false;
        mark("controls stay");
        walkTo(10, 0, false);
        ticks(70);
        if (!scene().equals("route")) throw stuck("no road: " + scene());
        mark("warp");

        walkTo(6, 17, false);                             // Tess sees you
        settle();
        if (!M_state__store.SESSION.save.flags.containsKey("beat_tess")) throw stuck("no fight with Tess: at " + scene() + " " + (hero()==null?"-":col()+","+row()) + " run=" + M_state__store.RUN.active + "/" + M_state__store.RUN.event + "@" + M_state__store.RUN.at + "/" + M_state__store.RUN.waiting + " won=" + M_state__store.BATTLE.won + " flags=" + M_state__store.SESSION.save.flags + " say=" + M_state__store.UI.say + " battles=" + battles);
        mark("trainer, line of sight");

        Monster lead = M_state__store.SESSION.save.team.get(0);
        for (int i = 0; i < 400 && (lead.level < 7 || M_state__store.SESSION.save.caught.size() < 3); i++) {
            backToTheRoad();
            walkTo(6, 14, false);                         // the reeds, back and forth
            backToTheRoad();
            walkTo(5, 14, true);
        }
        if (M_state__store.SESSION.save.caught.size() < 2) throw stuck("nothing caught in the reeds");
        if (lead.level < 7) throw stuck("no level 7");
        mark("wild battles, capture, levels, evolution: " + lead.species);

        walkTo(11, 12, true);                             // the knot in the grass
        face("right");
        pressA();
        settle();
        if (!M_state__store.SESSION.save.flags.containsKey("found_knot")) throw stuck("no knot found");
        mark("hide_if");

        walkTo(7, 12, true);
        walkTo(7, 8, false);                              // Bram
        walkTo(7, 7, false);
        settle();
        if (!M_state__store.SESSION.save.flags.containsKey("beat_bram")) throw stuck("no fight with Bram");
        mark("rival");
        walkTo(7, 3, false);                              // the door
        settle();
        if (!M_state__store.SESSION.save.flags.containsKey("lit")) throw stuck("the light is off");
        mark("the end");
        ticks(30);
        System.out.println("APKPYGAME_SUMMARY steps=" + step + " hash=" + game.stateHash() + " battles=" + battles + " lead="
                + lead.species + " L" + lead.level + " team=" + M_state__store.SESSION.save.team.size());

        // a new run, from the save made at the last warp: Continue
        Game second = Game.load(platform);
        second.start("title", "{}");
        second.viewport.update((int) second.config.width, (int) second.config.height);
        for (int i = 0; i < 20; i++) second.step();
        second.input.pointerDown(0, 240, 150);            // a quick tap, down and up in one step, where New journey will be
        second.input.pointerUp(0, 240, 150);
        for (int i = 0; i < 10; i++) second.step();
        if (second.scene().find("name_page").active) throw stuck("a quick tap on the title also pressed New journey");
        for (double[] at : new double[][]{{240, 190}}) {  // Continue
            second.input.pointerDown(0, at[0], at[1]);
            second.step();
            second.input.pointerUp(0, at[0], at[1]);
            for (int i = 0; i < 10; i++) second.step();
        }
        for (int i = 0; i < 120; i++) second.step();
        if (!second.scene().name.equals(M_state__store.SESSION.save.map)) throw stuck("Continue went to " + second.scene().name);
        if (M_state__store.SESSION.save.team.isEmpty()) throw stuck("Continue lost the team");
        Entity back = second.scene().find("hero");
        if (back.transform.x != 6.5 * 16 || back.transform.y != 24.5 * 16) {
            throw stuck("Continue put the hero at " + back.transform.x + "," + back.transform.y + ", not where the last warp arrived");
        }
        mark("continue");
        System.out.println("features: " + tried);
    }

    /** After a lost battle the hero wakes up at the Keeper's. */
    void backToTheRoad() {
        settle();
        if (scene().equals("house")) {
            mark("losing");
            walkTo(4, 5, false);
            push("down");
            ticks(70);
        }
        if (scene().equals("village")) {
            walkTo(10, 7, false);
            walkTo(10, 0, false);
            ticks(70);
        }
    }

    void drag(double x1, double y1, double x2, double y2, int n) {
        game.input.pointerDown(0, x1, y1);
        tick();
        for (int k = 1; k <= n; k++) {
            game.input.pointerMove(0, x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n);
            tick();
        }
        game.input.pointerUp(0, x2, y2);
        tick();
        ticks(40);
    }

    public static void main(String[] args) throws Exception {
        final File folder = new File(args[0]);
        HeadlessPlatform platform = new HeadlessPlatform(new Platform.AssetSource() {
            @Override public byte[] read(String p) throws java.io.IOException {
                return Files.readAllBytes(new File(folder, p).toPath());
            }

            @Override public boolean exists(String p) {
                return new File(folder, p).isFile();
            }
        });
        Bot bot = new Bot(platform);
        try {
            bot.play();
        } finally {
            Files.write(new File(args[1]).toPath(), bot.replay.toString().getBytes("UTF-8"));
        }
    }
}
