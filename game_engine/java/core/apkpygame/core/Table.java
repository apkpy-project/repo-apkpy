package apkpygame.core;

import apkpygame.core.json.Json;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A data table: SPECIES = table("data/species", Species) in a game module.
 * The build checked the rows against the @dataclass and wrote them to
 * tables/PATH.json in the bundle; they are made into objects the first time
 * the table is used, keyed by their "id". Read-only: the rows are not part of
 * the state (the bundle is the same for every run).
 */
public final class Table<T> {
    private final String path;
    private final Data.Maker<T> make;
    private Game loadedFor;
    private LinkedHashMap<String, T> rows;
    private ArrayList<T> all;

    public Table(String path, Data.Maker<T> make) {
        this.path = path;
        this.make = make;
    }

    private void load() {
        Game game = Game.current();
        if (rows != null && loadedFor == game) return;
        LinkedHashMap<String, T> byId = new LinkedHashMap<String, T>();
        ArrayList<T> list = new ArrayList<T>();
        for (Object row : (List<?>) Json.parse(game.assets.text("tables/" + path + ".json"))) {
            @SuppressWarnings("unchecked")
            Map<String, Object> o = (Map<String, Object>) row;
            T item = make.make(o);
            byId.put(String.valueOf(o.get("id")), item);
            list.add(item);
        }
        rows = byId;
        all = list;
        loadedFor = game;
    }

    /** TABLE.get("id"): the row, or a KeyError naming the table. */
    public T get(String id) {
        load();
        T row = rows.get(id);
        if (row == null) throw new Py.PyError("KeyError: '" + id + "' is not in " + path);
        return row;
    }

    public boolean has(String id) {
        load();
        return rows.containsKey(id);
    }

    /** Every row, in the order of the files. */
    public ArrayList<T> all() {
        load();
        return new ArrayList<T>(all);
    }

    public int size() {
        load();
        return all.size();
    }
}
