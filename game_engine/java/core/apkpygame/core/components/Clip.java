package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.RenderQueue;

/**
 * On the entity that holds a ScrollList's rows: they are drawn and tapped only
 * inside the list's box. The list's entity can have other children (a title, a
 * close button) that are not cut.
 */
final class Clip extends Component {
    final ScrollList list;

    Clip(ScrollList list) {
        this.list = list;
    }

    @Override protected boolean clipChildren(RenderQueue queue, Mat3 world) {
        return list.scissor(queue, world);
    }
}
