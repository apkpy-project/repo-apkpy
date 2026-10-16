"""Conditional Android runtime for Data Core query observation."""

from __future__ import annotations


def generate_files(package):
    return {
        "java/ApkpyDataInvalidationTracker.java": _tracker(package),
        "java/ApkpyQuerySubscription.java": _subscription(package),
    }


def _tracker(package):
    return f'''package {package};

import java.util.Set;
import java.util.concurrent.CopyOnWriteArrayList;

public final class ApkpyDataInvalidationTracker {{
    private static final CopyOnWriteArrayList<ApkpyQuerySubscription> OBSERVERS =
            new CopyOnWriteArrayList<>();
    private ApkpyDataInvalidationTracker() {{}}

    static void add(ApkpyQuerySubscription observer) {{
        if (observer != null && !OBSERVERS.contains(observer)) OBSERVERS.add(observer);
    }}
    static void remove(ApkpyQuerySubscription observer) {{ OBSERVERS.remove(observer); }}
    public static void invalidate(Set<String> models) {{
        for (ApkpyQuerySubscription observer : OBSERVERS) observer.invalidate(models);
    }}
    public static void invalidateAll() {{ invalidate(null); }}
}}
'''


def _subscription(package):
    return f'''package {package};

import android.content.Context;
import org.json.JSONArray;
import java.util.Set;

public final class ApkpyQuerySubscription {{
    private final Context context;
    private final String model;
    private final ApkpyDataExecutor.Callback callback;
    private JSONArray filters, order, include;
    private Integer limit;
    private int offset;
    private Set<String> dependencies;
    private boolean active=false, closed=false, running=false, pending=false, force=false;
    private int generation=0;
    private String snapshot=null;

    public ApkpyQuerySubscription(Context context,String model,JSONArray filters,
            JSONArray order,Integer limit,int offset,JSONArray include,
            ApkpyDataExecutor.Callback callback) {{
        this.context=context.getApplicationContext(); this.model=model;
        this.filters=filters==null?new JSONArray():filters;
        this.order=order==null?new JSONArray():order;
        this.limit=limit; this.offset=Math.max(0,offset);
        this.include=include==null?new JSONArray():include; this.callback=callback;
        this.dependencies=ApkpyDatabase.getInstance(context).queryDependencies(model,this.include);
        ApkpyDataInvalidationTracker.add(this);
    }}
    public synchronized void resume() {{ if(closed)return; active=true; refresh(); }}
    public synchronized void pause() {{ active=false; generation++; }}
    public synchronized void close() {{
        if(closed)return; closed=true; active=false; pending=false; generation++;
        ApkpyDataInvalidationTracker.remove(this);
    }}
    public synchronized void refresh() {{ if(closed||!active)return; force=true; schedule(); }}
    public synchronized void updateQuery(int mask,JSONArray filters,JSONArray order,
            Integer limit,Integer offset,JSONArray include) {{
        if(closed)return;
        if((mask&1)!=0)this.filters=filters==null?new JSONArray():filters;
        if((mask&2)!=0)this.order=order==null?new JSONArray():order;
        if((mask&4)!=0)this.limit=limit;
        if((mask&8)!=0)this.offset=offset==null?0:Math.max(0,offset);
        if((mask&16)!=0){{this.include=include==null?new JSONArray():include;
            this.dependencies=ApkpyDatabase.getInstance(context).queryDependencies(model,this.include);}}
        generation++; snapshot=null; force=true; if(running)pending=true; schedule();
    }}
    synchronized void invalidate(Set<String> models) {{
        if(closed||!active)return;
        if(models!=null){{boolean match=false;for(String name:models)if(dependencies.contains(name)){{match=true;break;}}if(!match)return;}}
        if(running)pending=true; schedule();
    }}
    private synchronized void schedule() {{
        if(closed||!active)return; if(running){{pending=true;return;}}
        running=true; pending=false; final int expected=generation; final boolean forced=force; force=false;
        ApkpyDataExecutor.submit(
            ()->ApkpyDatabase.getInstance(context).findSync(model,filters,order,limit,offset,include),
            new ApkpyDataExecutor.Callback(){{
                public void onResult(String value){{
                    ApkpyDataExecutor.Callback deliver=null;
                    synchronized(ApkpyQuerySubscription.this){{
                        if(!closed&&active&&expected==generation&&(forced||!value.equals(snapshot))){{snapshot=value;deliver=callback;}}
                    }}
                    if(deliver!=null)deliver.onResult(value); complete(expected);
                }}
                public void onError(String error){{
                    ApkpyDataExecutor.Callback deliver=null;
                    synchronized(ApkpyQuerySubscription.this){{if(!closed&&active&&expected==generation)deliver=callback;}}
                    if(deliver!=null)deliver.onError(error); complete(expected);
                }}
            }});
    }}
    private void complete(int expected) {{
        boolean rerun;
        synchronized(this){{running=false;rerun=!closed&&active&&(pending||expected!=generation);pending=false;}}
        if(rerun)schedule();
    }}
}}
'''


__all__ = ["generate_files"]
