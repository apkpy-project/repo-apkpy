"""pager() and tab(): tabs over pages that swipe -- the Android side.

A pager is a container marked ``_pager`` and each ``tab()`` a container
marked ``_tab`` inside it, so everything the compiler already does for a
container -- ids, shapes, drawables and callbacks inside a page -- keeps
working. The layout is::

    <LinearLayout id=pgrN_host vertical>
        <TabLayout id=pgrN_tabs/>          the strip, Material's own
        <View id=pgrN_divider/>            only with a border-color
        <ApkpyPager id=pgrN>
            <LinearLayout id=cntK/>        one per tab: its page
        </ApkpyPager>
    </LinearLayout>

ApkpyPager, below, lays the pages side by side, follows a finger, settles on
a page, drives the tab indicator and takes the height of the page on screen.
The Activity only finds it and hands it the tabs -- the logic lives in the
fixed class, not in generated code.

The colours and sizes come from ``theme.pager_colors``/``tab_bar_height``,
which the Previewer reads too.
"""

from ...theme import pager_colors, tab_bar_height, TAB_INDICATOR_HEIGHT

CODE = "U2040"


def is_pager(comp):
    return bool(comp.get('_pager'))


def tabs_of(comp):
    return [child for child in comp.get('children', []) if child.get('_tab')]


def bar_height(comp):
    tabs = tabs_of(comp)
    has_text = any(str(t.get('_tab_text') or '').strip() for t in tabs)
    has_icon = any(t.get('_tab_icon') for t in tabs)
    return tab_bar_height(has_text, has_icon)


def colors(style, tokens):
    return pager_colors(tokens, style)


def all_caps(style):
    """Material 2 tabs shout, as its buttons do; text-transform: none stops it."""
    value = str((style or {}).get('text-transform', '')).strip().lower()
    return value not in ('none', 'capitalize', 'lowercase')


def refuse_orphan_tab(line=0):
    from ...diagnostics import ApkpyError
    raise ApkpyError(
        'tab() needs a pager() as its parent.',
        code=CODE,
        title='A tab outside a pager',
        cause=('A tab is one page of a pager: its tab goes in the pager\'s '
               'strip and its components are the page. On its own it has '
               'nowhere to go.'),
        expected='tab("Posts", parent=tabs), where tabs = pager(...)',
        received='tab(...) without a pager parent',
        suggestions=[
            'tabs = pager(id="tabs", screen=home)',
            'posts = tab("Posts", icon="grid_on", parent=tabs)',
            'Put what the page shows inside it: label("...", parent=posts)',
        ],
        docs='https://repo-apkpy.pages.dev/ui-components/#tabs-that-swipe',
        line=line or 0,
    )


def layout_xml(number, indent, package, host_height, fills, margin_xml, background_xml,
               divider_xml, bar_dp, children_lines):
    """The host, the strip, the optional line and the pager holding the pages.

    ``host_height`` is the host's layout_height (and weight) attributes;
    ``fills`` says the host has a height of its own -- fixed, or grown in a
    column -- which the pager then fills below the strip. Otherwise both wrap
    and the pager takes the height of the page on screen."""
    jv = 'pgr%d' % number
    lines = [
        f'{indent}<LinearLayout',
        f'{indent}    android:id="@+id/{jv}_host"',
        f'{indent}    android:layout_width="match_parent"',
        f'{indent}    {host_height}{margin_xml}',
        f'{indent}    android:orientation="vertical">',
        '',
        f'{indent}    <com.google.android.material.tabs.TabLayout',
        f'{indent}        android:id="@+id/{jv}_tabs"',
        f'{indent}        android:layout_width="match_parent"',
        f'{indent}        android:layout_height="{bar_dp}dp"',
        f'{indent}        android:background="{background_xml}"',
        f'{indent}        app:tabMode="fixed"',
        f'{indent}        app:tabGravity="fill"',
        f'{indent}        app:tabIndicatorHeight="{TAB_INDICATOR_HEIGHT}dp"',
        f'{indent}        app:tabIndicatorFullWidth="true" />',
        '',
    ]
    if divider_xml:
        lines += [
            f'{indent}    <View',
            f'{indent}        android:id="@+id/{jv}_divider"',
            f'{indent}        android:layout_width="match_parent"',
            f'{indent}        android:layout_height="1dp"',
            f'{indent}        android:background="{divider_xml}" />',
            '',
        ]
    inner_height = (
        'android:layout_height="0dp"\n' + indent + '        android:layout_weight="1"'
        if fills else 'android:layout_height="wrap_content"')
    lines += [
        f'{indent}    <{package}.ApkpyPager',
        f'{indent}        android:id="@+id/{jv}"',
        f'{indent}        android:layout_width="match_parent"',
        f'{indent}        {inner_height}>',
        '',
    ]
    lines += children_lines
    lines += [
        f'{indent}    </{package}.ApkpyPager>',
        f'{indent}</LinearLayout>',
        '',
    ]
    return lines


def _java_string(value):
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def java_setup(number, indent, tabs, active_java, inactive_java, indicator_java, caps):
    """Find the pager and hand it the tabs: texts, icons, descriptions, colours."""
    jv = 'pgr%d' % number
    texts = ', '.join(_java_string(t.get('_tab_text')) for t in tabs)
    icons = ', '.join(('R.drawable.%s' % t['_tab_drawable']) if t.get('_tab_drawable') else '0'
                      for t in tabs)
    descriptions = ', '.join(
        _java_string(t.get('describe') if t.get('describe') is not None
                     else t.get('_tab_text')) for t in tabs)
    return [
        f'{indent}ApkpyPager {jv} = findViewById(R.id.{jv});',
        f'{indent}{jv}.attachTabs(findViewById(R.id.{jv}_tabs),',
        f'{indent}        new String[]{{{texts}}},',
        f'{indent}        new int[]{{{icons}}},',
        f'{indent}        new String[]{{{descriptions}}},',
        f'{indent}        {active_java}, {inactive_java}, {indicator_java}, {"true" if caps else "false"});',
    ]


JAVA = r'''package __PACKAGE__;

import android.animation.ValueAnimator;
import android.content.Context;
import android.content.res.ColorStateList;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.VelocityTracker;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
import android.widget.TextView;

import com.google.android.material.tabs.TabLayout;

/**
 * Pages side by side, one on screen: moved by a finger or by a tab.
 *
 * Generated by ApkPy for pager()/tab(). The page on screen sets the height
 * unless the layout fixes it, so a long grid and a short page can share a
 * pager in a scrolling screen. A drag past a fifth of the width, or a fling,
 * goes to the next page; the tab indicator follows the finger.
 */
public class ApkpyPager extends ViewGroup {
    private int current = 0;
    private float offset = 0f;
    private TabLayout tabs;
    private boolean syncing = false;
    private float downX, downY, lastX;
    private boolean dragging = false;
    private final int touchSlop;
    private final int flingVelocity;
    private VelocityTracker velocity;
    private ValueAnimator animator;

    public ApkpyPager(Context context) {
        this(context, null);
    }

    public ApkpyPager(Context context, AttributeSet attrs) {
        super(context, attrs);
        ViewConfiguration config = ViewConfiguration.get(context);
        touchSlop = config.getScaledTouchSlop();
        flingVelocity = config.getScaledMinimumFlingVelocity() * 4;
    }

    public int getCurrent() {
        return current;
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        int width = MeasureSpec.getSize(widthSpec);
        int heightMode = MeasureSpec.getMode(heightSpec);
        boolean fixed = heightMode == MeasureSpec.EXACTLY;
        int childWidth = MeasureSpec.makeMeasureSpec(width, MeasureSpec.EXACTLY);
        int childHeight = fixed
                ? MeasureSpec.makeMeasureSpec(MeasureSpec.getSize(heightSpec), MeasureSpec.EXACTLY)
                : MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED);
        for (int i = 0; i < getChildCount(); i++) {
            getChildAt(i).measure(childWidth, childHeight);
        }
        int height;
        if (fixed) {
            height = MeasureSpec.getSize(heightSpec);
        } else {
            View page = getChildCount() == 0 ? null
                    : getChildAt(Math.max(0, Math.min(getChildCount() - 1, current)));
            height = page == null ? 0 : page.getMeasuredHeight();
            if (heightMode == MeasureSpec.AT_MOST) {
                height = Math.min(height, MeasureSpec.getSize(heightSpec));
            }
        }
        setMeasuredDimension(width, height);
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        int width = r - l;
        for (int i = 0; i < getChildCount(); i++) {
            View page = getChildAt(i);
            page.layout(i * width, 0, i * width + width, page.getMeasuredHeight());
        }
        scrollTo(Math.round(offset * width), 0);
    }

    @Override
    public boolean onInterceptTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = lastX = event.getX();
                downY = event.getY();
                dragging = animator != null && animator.isRunning();
                if (dragging) {
                    animator.cancel();
                }
                break;
            case MotionEvent.ACTION_MOVE:
                float dx = event.getX() - downX;
                float dy = event.getY() - downY;
                if (!dragging && getChildCount() > 1 && Math.abs(dx) > touchSlop
                        && Math.abs(dx) > Math.abs(dy) * 1.2f) {
                    dragging = true;
                    lastX = event.getX();
                    if (getParent() != null) {
                        getParent().requestDisallowInterceptTouchEvent(true);
                    }
                }
                break;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                dragging = false;
                break;
        }
        return dragging;
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (velocity == null) {
            velocity = VelocityTracker.obtain();
        }
        velocity.addMovement(event);
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = lastX = event.getX();
                downY = event.getY();
                return true;
            case MotionEvent.ACTION_MOVE: {
                if (!dragging) {
                    if (getChildCount() < 2 || Math.abs(event.getX() - downX) <= touchSlop) {
                        return true;
                    }
                    dragging = true;
                    lastX = event.getX();
                    if (getParent() != null) {
                        getParent().requestDisallowInterceptTouchEvent(true);
                    }
                }
                float dx = event.getX() - lastX;
                lastX = event.getX();
                float max = Math.max(0, getChildCount() - 1);
                offset = Math.max(0f, Math.min(max, offset - dx / Math.max(1, getWidth())));
                scrollTo(Math.round(offset * getWidth()), 0);
                if (tabs != null) {
                    int left = (int) Math.floor(offset);
                    tabs.setScrollPosition(left, offset - left, true);
                }
                return true;
            }
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL: {
                float vx = 0f;
                if (velocity != null) {
                    velocity.computeCurrentVelocity(1000);
                    vx = velocity.getXVelocity();
                    velocity.recycle();
                    velocity = null;
                }
                if (dragging) {
                    dragging = false;
                    settle(vx);
                }
                return true;
            }
        }
        return super.onTouchEvent(event);
    }

    private void settle(float velocityX) {
        int target = current;
        float moved = offset - current;
        if (velocityX < -flingVelocity || moved > 0.2f) {
            target = current + 1;
        } else if (velocityX > flingVelocity || moved < -0.2f) {
            target = current - 1;
        }
        select(target, true);
    }

    /** Show page {@code index}, sliding to it when {@code animate}. */
    public void select(int index, boolean animate) {
        int count = getChildCount();
        if (count == 0) {
            return;
        }
        final int target = Math.max(0, Math.min(count - 1, index));
        boolean changed = target != current;
        current = target;
        if (animator != null) {
            animator.cancel();
        }
        if (changed) {
            // The height follows the page it lands on from the start.
            requestLayout();
        }
        int width = getWidth();
        if (!animate || width == 0 || Math.abs(offset - target) < 0.001f) {
            offset = target;
            scrollTo(target * width, 0);
            syncTabs(target, 0f);
            return;
        }
        animator = ValueAnimator.ofFloat(offset, target);
        animator.setDuration(250);
        animator.setInterpolator(new DecelerateInterpolator());
        animator.addUpdateListener(animation -> {
            offset = (float) animation.getAnimatedValue();
            scrollTo(Math.round(offset * getWidth()), 0);
            int left = (int) Math.floor(offset);
            syncTabs(left, offset - left);
        });
        animator.start();
    }

    private void syncTabs(int position, float fraction) {
        if (tabs == null) {
            return;
        }
        tabs.setScrollPosition(position, fraction, true);
        if (fraction == 0f) {
            TabLayout.Tab tab = tabs.getTabAt(position);
            if (tab != null && !tab.isSelected()) {
                syncing = true;
                tab.select();
                syncing = false;
            }
        }
    }

    /** The strip: one tab per page, in the pager's colours. */
    public void attachTabs(TabLayout strip, String[] texts, int[] icons, String[] descriptions,
                           int active, int inactive, int indicator, boolean allCaps) {
        tabs = strip;
        strip.setTabTextColors(inactive, active);
        strip.setSelectedTabIndicatorColor(indicator);
        strip.setTabIconTint(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_selected}, new int[]{}},
                new int[]{active, inactive}));
        for (int i = 0; i < texts.length; i++) {
            TabLayout.Tab tab = strip.newTab();
            if (texts[i] != null && !texts[i].isEmpty()) {
                tab.setText(texts[i]);
            }
            if (i < icons.length && icons[i] != 0) {
                tab.setIcon(icons[i]);
            }
            if (i < descriptions.length && descriptions[i] != null && !descriptions[i].isEmpty()) {
                tab.setContentDescription(descriptions[i]);
            }
            strip.addTab(tab, i == current);
            if (!allCaps) {
                for (int j = 0; j < tab.view.getChildCount(); j++) {
                    View child = tab.view.getChildAt(j);
                    if (child instanceof TextView) {
                        ((TextView) child).setAllCaps(false);
                    }
                }
            }
        }
        strip.addOnTabSelectedListener(new TabLayout.OnTabSelectedListener() {
            @Override
            public void onTabSelected(TabLayout.Tab tab) {
                if (!syncing) {
                    select(tab.getPosition(), true);
                }
            }

            @Override
            public void onTabUnselected(TabLayout.Tab tab) {
            }

            @Override
            public void onTabReselected(TabLayout.Tab tab) {
            }
        });
    }
}
'''


def generate_java(package):
    return JAVA.replace('__PACKAGE__', package)
