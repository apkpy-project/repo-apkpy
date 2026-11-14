package apkpygame.core;

import apkpygame.core.json.Json;
import apkpygame.core.math.Color;

import java.util.List;
import java.util.Map;

/** Reads scenes/{name}.json (format 1) into a Scene. */
final class SceneLoader {
    static final int FORMAT = 1;

    private SceneLoader() { }

    static Scene load(Game game, String name, Map<String, Object> args) {
        String path = "scenes/" + name + ".json";
        if (!game.assets.exists(path)) {
            throw new GameException("G3002", "there is no scene '" + name + "' in the game bundle",
                    "Check the name given to game_play(), and that the scene was declared in the game.");
        }
        Map<String, Object> o;
        try {
            o = Json.parseObject(game.assets.text(path));
        } catch (IllegalArgumentException e) {
            throw new GameException("G3003", path + " is not valid JSON: " + e.getMessage(),
                    "Rebuild the game with apkpygame build.", e);
        }
        int format = (int) Json.num(o, "format", FORMAT);
        if (format > FORMAT) {
            throw new GameException("G3001", path + " is format " + format + ", this engine reads up to " + FORMAT,
                    "Update the ApkPyGame engine.");
        }
        String kind = Json.str(o, "kind", "2d");
        if (!kind.equals("2d") && !kind.equals("2.5d")) {
            throw new GameException("G3004", "scene '" + name + "' is a '" + kind + "' scene",
                    "This engine version runs \"2d\" and \"2.5d\" scenes.");
        }
        Scene scene = new Scene(game, name, kind, args);
        scene.background = Color.parse(Json.str(o, "background", null), game.config.background);
        Map<String, Object> music = Json.obj(o, "music");
        if (music != null) {
            scene.music = Json.str(music, "path", null);
            scene.musicVolume = Json.num(music, "volume", 1);
            scene.musicLoop = Json.bool(music, "loop", true);
        }
        scene.onBack.addAll(Actions.read(Json.list(o, "on_back"), game));
        Map<String, Object> cam = Json.obj(o, "camera");
        if (cam != null) {
            scene.camera.x = Json.num(cam, "x", scene.camera.x);
            scene.camera.y = Json.num(cam, "y", scene.camera.y);
            scene.camera.zoom = Json.num(cam, "zoom", 1);
            scene.camera.rotation = Json.num(cam, "rotation", 0);
            scene.follow = Json.str(cam, "follow", null);
            if (scene.camera3d != null) {
                scene.camera3d.pitch = Json.num(cam, "pitch", scene.camera3d.pitch);
                scene.camera3d.yaw = Json.num(cam, "yaw", scene.camera3d.yaw);
                scene.camera3d.distance = Json.num(cam, "distance", scene.camera3d.distance);
                scene.camera3d.fov = Json.num(cam, "fov", scene.camera3d.fov);
                scene.cameraElevation = Json.num(cam, "elevation", 0);
                List<Object> fog = Json.list(cam, "fog");
                if (fog.size() == 2) {
                    scene.view3d.fogStart = ((Number) fog.get(0)).doubleValue();
                    scene.view3d.fogEnd = ((Number) fog.get(1)).doubleValue();
                    scene.view3d.fogColor = scene.background;
                }
            }
            List<Object> b = Json.list(cam, "bounds");
            if (b.size() == 4) {
                scene.cameraBounds = new double[]{((Number) b.get(0)).doubleValue(), ((Number) b.get(1)).doubleValue(),
                        ((Number) b.get(2)).doubleValue(), ((Number) b.get(3)).doubleValue()};
            }
        }
        Map<String, Object> vars = Json.obj(o, "vars");
        if (vars != null) {
            for (Map.Entry<String, Object> v : vars.entrySet()) {
                if (v.getValue() instanceof Number) game.setVar(v.getKey(), ((Number) v.getValue()).doubleValue());
            }
        }
        for (Object item : Json.list(o, "rules")) {
            Map<String, Object> r = asObject(item, path + " rules");
            scene.rules.add(new Scene.Rule(Json.str(r, "var", null), Json.str(r, "count", null), Json.str(r, "op", "=="),
                    Json.num(r, "value", 0), Actions.read(Json.list(r, "actions"), game)));
        }
        for (Object item : Json.list(o, "entities")) {
            scene.spawn(entity(game, asObject(item, path)));
        }
        return scene;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asObject(Object item, String where) {
        if (!(item instanceof Map)) {
            throw new GameException("G3003", where + ": an entity has to be an object", "Rebuild the game.");
        }
        return (Map<String, Object>) item;
    }

    static Entity entity(Game game, Map<String, Object> o) {
        Entity e = new Entity(Json.str(o, "name", ""));
        for (Object tag : Json.list(o, "tags")) e.addTag(String.valueOf(tag));
        e.active = Json.bool(o, "active", true);
        e.ui = Json.bool(o, "ui", false);
        e.group = Json.str(o, "group", null);
        e.persistent = Json.bool(o, "persistent", false);
        e.marker = Json.str(o, "marker", null);
        double[] anchor = Json.pair(o, "anchor", 0, 0);
        e.anchorX = anchor[0];
        e.anchorY = anchor[1];
        Map<String, Object> props = Json.obj(o, "props");
        if (props != null) e.props = new Props(props);
        Map<String, Object> t = Json.obj(o, "transform");
        if (t != null) {
            e.transform.x = Json.num(t, "x", 0);
            e.transform.y = Json.num(t, "y", 0);
            e.transform.rotation = Json.num(t, "rotation", 0);
            e.transform.elevation = Json.num(t, "elevation", 0);
            double[] scale = Json.pair(t, "scale", 1, 1);
            e.transform.scaleX = scale[0];
            e.transform.scaleY = scale[1];
        }
        List<Object> components = Json.list(o, "components");
        for (Object item : components) {
            Map<String, Object> c = asObject(item, "components");
            String type = Json.str(c, "type", "");
            ComponentTypes.Reader reader = ComponentTypes.find(type);
            if (reader == null) {
                // a newer build with a component this engine does not have: keep running
                game.platform.logger().warn("G3005 unknown component type '" + type + "' on '" + e.name
                        + "' (ignored; update the engine)");
                continue;
            }
            e.add(reader.read(c, game));
        }
        for (Object child : Json.list(o, "children")) e.addChild(entity(game, asObject(child, "children")));
        return e;
    }
}
