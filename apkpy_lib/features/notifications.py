"""Persistent notification drawer rendered inside the Previewer's device."""
from collections import OrderedDict
import time
from ..core.features.notifications import IMPORTANCE, STYLES, MAX_ACTIONS, REASONS, DEFAULT_CHANNEL, validate


class NotificationsAPI:
    def __init__(self):
        self.channels = {}
        self.items = OrderedDict()
        self._allowed = True
        self._drawer = None

    def channel(self, id, name, importance="default"):
        if importance not in IMPORTANCE:
            raise ValueError("importance must be min, low, default or high")
        if not str(id).strip() or not str(name).strip():
            raise ValueError("Channel id and name cannot be empty")
        old = self.channels.get(str(id))
        self.channels[str(id)] = {"name": str(name), "importance": old["importance"] if old else importance}

    def allowed(self):
        return self._allowed

    def ask(self):
        drawer = self._ensure()
        if drawer:
            drawer.permission()

    def cancel(self, id):
        self.items.pop(str(id), None)
        self._refresh()

    def cancel_all(self):
        self.items.clear()
        self._refresh()

    def _ensure(self):
        from .. import ui
        app = ui.live_preview()
        if app is None:
            return None
        if self._drawer is None or self._drawer.app is not app:
            self._drawer = _Drawer(app, self)
        return self._drawer

    def _refresh(self):
        if not self.items and self._drawer is None:
            return
        from .. import ui
        root = ui.live_preview_root()
        if root is None:
            return
        def paint():
            drawer = self._ensure()
            if drawer:
                drawer.refresh()
        # notify can be called by a background-job thread. Never build Tk there.
        import threading
        if threading.current_thread() is threading.main_thread():
            paint()
        else:
            root.after(0, paint)

    def _invoke(self, callback):
        if callback is None:
            return
        from .. import ui
        if isinstance(callback, ui.Screen):
            app = ui.live_preview()
            if app:
                app.render_screen(callback)
        else:
            callback()

    def _tap(self, id):
        item = self.items.get(id)
        if item is None:
            return
        if not item["ongoing"]:
            self.items.pop(id, None)
        if self._drawer:
            self._drawer.close()
        self._refresh()
        self._invoke(item["on_tap"])

    def _action(self, id, index):
        item = self.items.get(id)
        if item is not None:
            if self._drawer:
                self._drawer.close()
                self._drawer.hide_banner()
            self._invoke(item["actions"][index][1])

    def _dismiss(self, id):
        item = self.items.get(id)
        if item is None or item["ongoing"]:
            return False
        self.items.pop(id)
        self._refresh()
        self._invoke(item["on_dismiss"])
        return True

    def _post(self, title, message, id, **kw):
        validate(kw["style"], kw["picture"], kw["lines"], kw["actions"], kw["progress"])
        from .. import ui
        from .. import icons
        if not isinstance(kw["icon"], str) or icons.resolve(kw["icon"]) is None:
            raise ValueError("Choose a notification icon from the icon catalogue")
        if kw["when"] is not None:
            import math
            if isinstance(kw["when"], bool) or not isinstance(kw["when"], (int, float)) or not math.isfinite(kw["when"]):
                raise ValueError("when must be an epoch timestamp in milliseconds")
        import threading
        root = ui.live_preview_root()
        if root is not None and threading.current_thread() is not threading.main_thread():
            root.after(0, lambda: self._post(title, message, id, **kw))
            return
        for callback in [kw["on_dismiss"]] + [x[1] for x in kw["actions"] or []]:
            if callback is not None and not callable(callback):
                raise ValueError("Notification callbacks must be callable")
        if kw["on_tap"] is not None and not (callable(kw["on_tap"]) or isinstance(kw["on_tap"], ui.Screen)):
            raise ValueError("on_tap must be a callback or Screen")
        if kw["channel"] == DEFAULT_CHANNEL:
            self.channel(DEFAULT_CHANNEL, "App notifications")
        if kw["channel"] not in self.channels:
            raise ValueError("Unknown notification channel: " + str(kw["channel"]))
        if not self.allowed():
            return
        id = str(id)
        previous = self.items.pop(id, {})
        self.items[id] = dict(kw, id=id, title=str(title), message=str(message),
                              actions=list(kw["actions"] or []), lines=list(kw["lines"] or []),
                              expanded=previous.get("expanded", False),
                              timestamp=kw["when"] if kw["when"] is not None else int(time.time()*1000))
        self._refresh()
        root = ui.live_preview_root()
        if root and self.channels[kw["channel"]]["importance"] == "high":
            root.after(0, lambda: self._ensure().heads_up(id))


class _Drawer:
    def __init__(self, app, api):
        import tkinter as tk
        self.app, self.api = app, api
        self.panel = None
        self.shell = None
        self.header = None
        self.banner = None
        self.banner_id = None
        self.banner_timer = None
        self.banner_animation = None
        self.animation = None
        self.photos = []
        self.permission_mode = False
        self.action_commands = {}
        self.indicator = tk.Canvas(app._status_frame, width=80, height=24, bd=0, highlightthickness=0)
        self.indicator.pack(side="left")
        for widget in (app._status_frame, app._status_clock, app._status_icons, self.indicator):
            widget.bind("<ButtonPress-1>", self._press, add="+")
            widget.bind("<ButtonRelease-1>", self._release, add="+")
        app.root.bind("<Escape>", self._escape, add="+")
        app.root.bind("<Configure>", self._resize, add="+")
        self._drag = None
        self._progress_tick = None
        self._progress_tracks = {}
        self._fonts = {}
        self._resize_pending = None
        self.refresh()

    def colors(self):
        from .. import ui
        tokens = ui.global_styles.get("__theme__", {})
        c = {k: tokens.get(k, default) for k, default in (
            ("surface", "#211F26"), ("text", "#E6E1E5"),
            ("text_secondary", "#CAC4D0"), ("primary", "#D0BCFF"), ("background", "#141218"))}
        # A light drawer needs a light surface, not a black overlay flattened
        # into an opaque grey. Keep both palettes derived from the app theme.
        rgb = self.app.root.winfo_rgb(c["background"])
        dark = sum(rgb) < 3 * 32768
        c["shade"] = ui._mix_color(c["background"], c["surface"], .22) if dark else ui._mix_color(c["background"], c["text"], .045)
        c["card"] = ui._mix_color(c["surface"], "#FFFFFF", .035 if dark else .65)
        c["soft"] = ui._mix_color(c["card"], c["primary"], .15 if dark else .11)
        c["line"] = ui._mix_color(c["card"], c["text"], .09)
        c["muted"] = ui._mix_color(c["card"], c["text"], .65)
        return c

    def font(self, size, bold=False):
        import tkinter.font as tkfont
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(root=self.app.root, family="Segoe UI",
                size=-size, weight="bold" if bold else "normal")
        return self._fonts[key]

    def fit(self, text, width, font):
        text = str(text).replace("\n", " ")
        if font.measure(text) <= width:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.measure(text[:mid] + "…") <= width:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + "…"

    def compact_body(self, text, width):
        font = self.font(14)
        text = " ".join(str(text).split())
        if font.measure(text) <= width:
            return text
        first = self.fit(text, width, font).rstrip("…")
        split = first.rfind(" ")
        if split > len(first) // 2:
            first = first[:split]
        return first + "\n" + self.fit(text[len(first):].lstrip(), width, font)

    def control(self, canvas, x, y, width, height, tag, command, c, label=None, glyph=None, filled=False):
        from .. import ui
        color = c["soft"] if filled else c["card"]
        surface = ui._create_rounded_rect(canvas,x,y,x+width,y+height,min(18,height/2),
            fill=color,outline=color,tags=tag)
        if label is not None:
            canvas.create_text(x+width/2,y+height/2,text=label,width=width-20,
                fill=c["primary"],font=self.font(13,True),justify="center",tags=tag)
        if glyph == "close":
            cx, cy = x+width/2, y+height/2
            canvas.create_line(cx-4,cy-4,cx+4,cy+4,fill=c["muted"],width=1.6,capstyle="round",tags=tag)
            canvas.create_line(cx+4,cy-4,cx-4,cy+4,fill=c["muted"],width=1.6,capstyle="round",tags=tag)
        elif glyph in ("up", "down"):
            cx, cy = x+width/2, y+height/2
            d = -1 if glyph == "up" else 1
            canvas.create_line(cx-4,cy-2*d,cx,cy+2*d,cx+4,cy-2*d,
                fill=c["muted"],width=1.6,capstyle="round",joinstyle="round",tags=tag)
        if command is not None:
            def hover(active):
                canvas.itemconfigure(surface,fill=c["soft"] if active else color,
                                     outline=c["soft"] if active else color)
                canvas.configure(cursor="hand2" if active else "")
            canvas.tag_bind(tag,"<Enter>",lambda e:hover(True))
            canvas.tag_bind(tag,"<Leave>",lambda e:hover(False))
            canvas.tag_bind(tag,"<Button-1>",lambda e:command())
        return surface

    def _press(self, event):
        self._drag = (event.x_root, event.y_root)

    def _release(self, event):
        self.open()
        return "break"

    def _escape(self, event=None):
        if self.panel:
            self.close()
            return "break"

    def _resize(self, event):
        if event.widget is self.app.root and self.panel and not self._resize_pending:
            def redraw():
                self._resize_pending = None
                self.draw()
            self._resize_pending = self.app.root.after_idle(redraw)

    def refresh(self):
        from .. import ui
        c = self.colors()
        fg, bg = getattr(self.app, "_status_palette", (c["text"],c["surface"]))
        self.indicator.configure(bg=bg)
        self.indicator.delete("all")
        for i, item in enumerate(list(self.api.items.values())[-3:]):
            ui._draw_material_icon(self.indicator, item["icon"], 10+i*20, 12, fg, size=14)
        if len(self.api.items)>3:
            self.indicator.create_text(71,12,text="•••",fill=fg,font=("Arial",7))
        if self.banner_id not in self.api.items:
            self.hide_banner()
        if self.panel:
            self.draw()

    def open(self):
        import tkinter as tk
        self.hide_banner()
        if self.panel:
            self.draw()
            return
        self.shell = tk.Frame(self.app.root,bd=0)
        self.shell.place(x=0,y=-self.app.root.winfo_height(),relwidth=1,height=max(100,self.app.root.winfo_height()-24))
        self.header = tk.Canvas(self.shell,height=102,bd=0,highlightthickness=0)
        self.header.pack(side="top",fill="x")
        self.header.bind("<ButtonPress-1>",self._press,add="+")
        self.header.bind("<ButtonRelease-1>",self._panel_release,add="+")
        self.panel = tk.Canvas(self.shell,bd=0,highlightthickness=0,yscrollincrement=16)
        self.panel.pack(side="top",fill="both",expand=True)
        self.shell.tk.call("raise", self.shell._w)
        self.panel.bind("<MouseWheel>", self._wheel)
        self.panel.bind("<ButtonPress-1>", self._press, add="+")
        self.panel.bind("<ButtonRelease-1>", self._panel_release, add="+")
        self.draw()
        self._animate(0)

    def _animate(self, step):
        if not self.panel:
            return
        t=min(1,step/12)
        self.shell.place_configure(y=int(24-(1-t)**3*self.app.root.winfo_height()))
        if step<12:
            self.animation=self.app.root.after(15,lambda:self._animate(step+1))
        else:
            self.animation=None

    def _wheel(self,event):
        if self.panel:
            self.panel.yview_scroll(-int(event.delta/120)*3,"units")
        return "break"

    def close(self):
        if self.animation:
            self.app.root.after_cancel(self.animation)
            self.animation=None
        if self._progress_tick:
            self.app.root.after_cancel(self._progress_tick)
            self._progress_tick=None
        if self._resize_pending:
            self.app.root.after_cancel(self._resize_pending)
            self._resize_pending=None
        if self.shell:
            self.shell.destroy()
        self.shell=self.panel=self.header=None
        self.permission_mode=False

    def _panel_release(self, event):
        if self._drag and event.y_root-self._drag[1] < -75:
            self.close()

    def permission(self):
        self.permission_mode=True
        self.open()

    def draw(self):
        if not self.panel:
            return
        from .. import ui
        canvas=self.panel
        c=self.colors()
        canvas.configure(bg=c["shade"])
        self.shell.configure(bg=c["shade"])
        self.shell.place_configure(height=max(100,self.app.root.winfo_height()-24))
        self.header.configure(bg=c["shade"])
        self.header.delete("all")
        previous_offset = max(0,canvas.canvasy(0))
        canvas.delete("all")
        self.photos=[]
        self.action_commands={}
        self._progress_tracks={}
        width=max(240,self.app.root.winfo_width())
        content_width=min(560,width-32)
        left=(width-content_width)/2
        header=self.header
        header.create_line(width/2-16,10,width/2+16,10,fill=c["line"],width=4,capstyle="round")
        header.create_text(left+2,37,text="Notifications",anchor="w",fill=c["text"],font=self.font(23,True))
        self.control(header,left+content_width-36,21,36,36,"close",self.close,c,glyph="close")
        count=len(self.api.items)
        summary="All caught up" if not count else "%d notification%s"%(count,"" if count==1 else "s")
        header.create_text(left+2,76,text=summary,anchor="w",fill=c["muted"],font=self.font(12))
        if any(not item["ongoing"] for item in self.api.items.values()):
            self.control(header,left+content_width-86,60,86,32,"clear",self._clear,c,label="Clear all",filled=True)
        y=4
        if self.permission_mode:
            y=self._permission_card(canvas,content_width,y,c,left)
        if not self.api.items and not self.permission_mode:
            cy=max(116,(self.app.root.winfo_height()-126)*.32)
            canvas.create_oval(width/2-36,cy-36,width/2+36,cy+36,fill=c["soft"],outline="")
            ui._draw_material_icon(canvas,"notifications",width/2,cy,c["primary"],size=28)
            canvas.create_text(width/2,cy+66,text="You're all caught up",fill=c["text"],font=self.font(19,True))
            canvas.create_text(width/2,cy+96,text="New notifications will appear here.",fill=c["muted"],font=self.font(13),width=content_width-32)
            y=cy+132
        groups={}
        for item in self.api.items.values():
            if item["group"]:
                groups[item["group"]]=groups.get(item["group"],0)+1
        seen=set()
        ordered=list(reversed(list(self.api.items.values())))
        display=[]
        for item in ordered:
            group=item["group"]
            if group and groups[group]>1:
                if group in seen:
                    continue
                seen.add(group)
                display.extend(i for i in ordered if i["group"]==group)
            else:
                display.append(item)
        seen=set()
        for item in display:
            group=item["group"]
            if group and groups[group]>1 and group not in seen:
                channel=self.api.channels.get(item["channel"],{})
                group_name=channel.get("name") or str(group)
                canvas.create_text(left+6,y+15,text=self.fit(group_name,content_width-54,self.font(12,True)),
                    anchor="w",fill=c["muted"],font=self.font(12,True))
                canvas.create_text(left+content_width-8,y+15,text=str(groups[group]),anchor="e",fill=c["muted"],font=self.font(12))
                y+=36
                seen.add(group)
            y=self.card(canvas,item,left,y,content_width,c)+12
        total=max(y+16,self.app.root.winfo_height()-126)
        canvas.configure(scrollregion=(0,0,width,total))
        canvas.yview_moveto(previous_offset/total)
        self._tick()

    def _permission_card(self, canvas, width, y, c, left=16):
        from .. import ui
        surface=ui._create_rounded_rect(canvas,left,y,left+width,y+194,24,fill=c["card"],outline=c["card"])
        ui._draw_material_icon(canvas,"notifications",left+32,y+32,c["primary"],size=22)
        canvas.create_text(left+18,y+57,text="Stay in the loop",anchor="nw",fill=c["text"],font=self.font(19,True))
        message=canvas.create_text(left+18,y+87,text="Allow this app to show notifications in the preview?",anchor="nw",fill=c["muted"],width=width-36,font=self.font(14))
        top=canvas.bbox(message)[3]+18
        canvas.delete(surface)
        surface=ui._create_rounded_rect(canvas,left,y,left+width,max(y+194,top+58),24,fill=c["card"],outline=c["card"])
        canvas.tag_lower(surface)
        slot=(width-48)/2
        self.control(canvas,left+18,top,slot,40,"permission_False",lambda:self._grant(False),c,label="Not now")
        self.control(canvas,left+30+slot,top,slot,40,"permission_True",lambda:self._grant(True),c,label="Allow",filled=True)
        return max(y+194,top+58)+16

    def _grant(self, value):
        self.api._allowed=value
        self.permission_mode=False
        self.draw()

    def _clear(self):
        for id in list(self.api.items):
            self.api._dismiss(id)

    def card(self, canvas, item, x, y, width, c, banner=False):
        from .. import ui
        import hashlib
        key="card_"+hashlib.sha256(item["id"].encode()).hexdigest()[:16]
        surface=ui._create_rounded_rect(canvas,x,y,x+width,y+140,24,fill=c["card"],outline=c["card"],tags=key)
        canvas.create_oval(x+18,y+16,x+50,y+48,fill=c["soft"],outline="",tags=key)
        ui._draw_material_icon(canvas,item["icon"],x+34,y+32,c["primary"],size=19,tags=key)
        app_bar=getattr(self.app._active_screen,'app_bar',None)
        name="ApkPy"
        if app_bar is not None:
            name=getattr(app_bar, 'kwargs', {}).get('title') or name
        controls=72 if not item["ongoing"] else 36
        meta=self.fit(str(name)+" · "+self.age(item["timestamp"]),width-76-controls,self.font(12))
        canvas.create_text(x+60,y+32,text=meta,anchor="w",fill=c["muted"],font=self.font(12),tags=key)
        self.control(canvas,x+width-controls-10,y+14,32,36,key+"_expand",
            lambda k=item["id"]:self._expand(k),c,glyph="up" if item["expanded"] else "down")
        if not item["ongoing"]:
            self.control(canvas,x+width-42,y+14,32,36,key+"_dismiss",
                lambda k=item["id"]:self.api._dismiss(k),c,glyph="close")
        title=canvas.create_text(x+18,y+60,text=item["title"],anchor="nw",width=width-36,
            fill=c["text"],font=self.font(17,True),tags=key)
        by=canvas.bbox(title)[3]+7
        body=item["message"] if item["expanded"] else self.compact_body(item["message"],width-38)
        body_id=canvas.create_text(x+18,by,text=body,anchor="nw",width=width-36,
            fill=c["muted"],font=self.font(14),tags=key)
        bottom=canvas.bbox(body_id)[3]+18
        if item["expanded"] and item["style"]=="inbox":
            bottom+=2
            for line in item["lines"]:
                canvas.create_oval(x+19,bottom+6,x+23,bottom+10,fill=c["primary"],outline="",tags=key)
                line_id=canvas.create_text(x+34,bottom,text=line,anchor="nw",width=width-52,
                    fill=c["text"],font=self.font(14),tags=key)
                bottom=canvas.bbox(line_id)[3]+12
        if item["expanded"] and item["style"]=="big_picture":
            try:
                from PIL import Image,ImageTk,ImageDraw
                with Image.open(item["picture"]) as image:
                    image.thumbnail((int(width-36),200),Image.Resampling.LANCZOS)
                    rounded=image.convert("RGBA")
                mask=Image.new("L",rounded.size,0)
                ImageDraw.Draw(mask).rounded_rectangle((0,0,rounded.width-1,rounded.height-1),radius=12,fill=255)
                rounded.putalpha(mask)
                photo=ImageTk.PhotoImage(rounded,master=canvas)
                self.photos.append(photo)
                canvas.create_image(x+width/2,bottom,image=photo,anchor="n",tags=key)
                bottom+=photo.height()+18
            except (OSError,ValueError):
                error=canvas.create_text(x+18,bottom,text="Picture unavailable in preview",anchor="nw",
                    width=width-36,fill=c["muted"],font=self.font(13),tags=key)
                bottom=canvas.bbox(error)[3]+18
        if item["progress"] is not None:
            caption="Complete" if item["progress"]==100 else "In progress"
            canvas.create_text(x+18,bottom,text=caption,anchor="nw",fill=c["muted"],font=self.font(12),tags=key)
            if item["progress"]!="indeterminate":
                canvas.create_text(x+width-18,bottom,text="%g%%"%float(item["progress"]),anchor="ne",
                    fill=c["primary"],font=self.font(12,True),tags=key)
            bottom+=27
            canvas.create_line(x+21,bottom,x+width-21,bottom,fill=c["soft"],width=6,capstyle="round",tags=key)
            fraction=.25 if item["progress"]=="indeterminate" else float(item["progress"])/100
            if fraction>0:
                canvas.create_line(x+21,bottom,x+21+(width-42)*fraction,bottom,
                    fill=c["primary"],width=6,capstyle="round",tags=(key,"progress_"+item["id"]))
            if item["progress"]=="indeterminate" and not banner:
                self._progress_tracks["progress_"+item["id"]]=(x+21,bottom,width-42)
            bottom+=23
        if item["actions"]:
            # Real pill-shaped hit targets, with natural widths and wrapped
            # labels on small viewports. No forced uppercase or stretched gaps.
            max_width=(width-36-8*(len(item["actions"])-1))/len(item["actions"])
            buttons=[]
            action_height=38
            for label,callback in item["actions"]:
                bw=min(max_width,max(76,self.font(13,True).measure(str(label))+28))
                measure=canvas.create_text(0,0,text=str(label),width=bw-20,font=self.font(13,True),anchor="nw")
                box=canvas.bbox(measure)
                action_height=max(action_height,box[3]-box[1]+18)
                canvas.delete(measure)
                buttons.append((str(label),bw))
            action_x=x+18
            for i,(label,callback) in enumerate(item["actions"]):
                tag=key+"_action_"+str(i)
                command=lambda k=item["id"],n=i:self.api._action(k,n)
                self.action_commands[(item["id"],i)]=command
                label,bw=buttons[i]
                self.control(canvas,action_x,bottom,bw,action_height,tag,command,c,label=label,filled=True)
                action_x+=bw+8
            bottom+=action_height+18
        canvas.delete(surface)
        # A heads-up floats over the app, so its edge is drawn; in the drawer
        # the cards sit on the shade and need none.
        surface=ui._create_rounded_rect(canvas,x,y,x+width,bottom,24,fill=c["card"],
            outline=c["line"] if banner else c["card"],tags=key)
        canvas.tag_lower(surface)
        canvas.tag_bind(key,"<ButtonPress-1>",self._press)
        canvas.tag_bind(key,"<ButtonRelease-1>",lambda e,k=item["id"]:self._card_release(e,k))
        return bottom

    def _card_release(self,event,id):
        if self._drag and abs(event.x_root-self._drag[0])>60:
            self.api._dismiss(id)
        elif not self._drag or abs(event.y_root-self._drag[1])<20:
            self.api._tap(id)

    def _expand(self,id):
        item=self.api.items.get(id)
        if item:
            item["expanded"]=not item["expanded"]
            if self.panel:
                self.draw()
            elif self.banner_id == id:
                self.heads_up(id)

    @staticmethod
    def age(timestamp):
        minutes=max(0,int((time.time()*1000-float(timestamp))/60000))
        return "now" if not minutes else (str(minutes)+"m" if minutes<60 else str(minutes//60)+"h")

    def heads_up(self,id):
        import tkinter as tk
        from .. import ui
        if self.panel or id not in self.api.items:
            return
        self.hide_banner()
        self.banner_id=id
        c=self.colors()
        w=max(240,self.app.root.winfo_width())
        content_width=min(560,w-24)
        # The card floats over the app, as Android's heads-up does, instead of
        # sitting on a band across the window. A Tk canvas cannot be
        # see-through, so it is only as big as the card, and the four corners
        # outside the rounding take the colour of what is under each one.
        self.banner=tk.Canvas(self.app.root,bg=c["card"],bd=0,highlightthickness=0)
        for corner in ("nw","ne","sw","se"):
            self.banner.create_rectangle(0,0,0,0,width=0,tags=("corner","corner_"+corner))
        bottom=self.card(self.banner,self.api.items[id],0,0,content_width,c,True)
        width,height=content_width,bottom+1
        half_w,half_h=width/2,height/2
        for corner,(x0,y0) in (("nw",(0,0)),("ne",(half_w,0)),("sw",(0,half_h)),("se",(half_w,half_h))):
            self.banner.coords("corner_"+corner,x0,y0,x0+half_w,y0+half_h)
        self.banner.tag_lower("corner")
        self._banner_box=(int((w-content_width)/2),width,height)
        self.banner.place(x=self._banner_box[0],y=-height,width=width,height=height)
        self.banner.tk.call("raise", self.banner._w)
        self._animate_banner(0, height, False)
        self.banner_timer=self.app.root.after(4000,lambda:self._animate_banner(0,height,True))

    def _colour_under(self, x, y):
        """The colour the app shows at (x, y) of the window, without the
        banner: the topmost filled shape of a canvas there, else the
        background of the widget there."""
        root=self.app.root
        left,top=root.winfo_rootx(),root.winfo_rooty()
        widget=root
        while True:
            inner=None
            # winfo children lists the stack bottom first: the last hit is on top.
            for child in widget.winfo_children():
                try:
                    if child is self.banner or child.winfo_class()=="Toplevel" or not child.winfo_ismapped():
                        continue
                    cx,cy=child.winfo_rootx()-left,child.winfo_rooty()-top
                    if cx<=x<cx+child.winfo_width() and cy<=y<cy+child.winfo_height():
                        inner=child
                except Exception:
                    pass
            if inner is None:
                break
            widget=inner
        try:
            if widget.winfo_class()=="Canvas":
                px=widget.canvasx(x-(widget.winfo_rootx()-left))
                py=widget.canvasy(y-(widget.winfo_rooty()-top))
                for item in reversed(widget.find_overlapping(px,py,px,py)):
                    if widget.type(item) in ("rectangle","oval","polygon","arc"):
                        fill=widget.itemcget(item,"fill")
                        if fill:
                            return fill
            return widget.cget("background")
        except Exception:
            return None

    def _paint_corners(self, y):
        """Each corner of the banner, at height y, in the colour under it."""
        if self.banner is None:
            return
        x,width,height=self._banner_box
        for corner,(px,py) in (("nw",(x+3,y+3)),("ne",(x+width-4,y+3)),
                               ("sw",(x+3,y+height-4)),("se",(x+width-4,y+height-4))):
            colour=self._colour_under(px,py)
            if colour:
                self.banner.itemconfigure("corner_"+corner,fill=colour)

    def _animate_banner(self, step, height, closing):
        self.banner_animation=None
        if self.banner is None:
            return
        t=min(1,step/12)
        progress=t*t if closing else (1-t)**3
        # The card's top edge ends 6 px below the 24 px status strip.
        y=int(30-(height+30)*progress)
        self.banner.place_configure(y=y)
        self._paint_corners(y)
        if step<12:
            self.banner_animation=self.app.root.after(15,lambda:self._animate_banner(step+1,height,closing))
        elif closing:
            self.hide_banner()

    def hide_banner(self):
        if self.banner_animation:
            self.app.root.after_cancel(self.banner_animation)
            self.banner_animation=None
        if self.banner_timer:
            self.app.root.after_cancel(self.banner_timer)
            self.banner_timer=None
        if self.banner:
            self.banner.destroy()
            self.banner=None
        self.banner_id=None
        # The item stays in api.items. Only the temporary heads-up disappears.

    def _tick(self):
        if self._progress_tick or not any(i["progress"] == "indeterminate" for i in self.api.items.values()):
            return
        def step():
            self._progress_tick=None
            if not self.panel:
                return
            import math
            fraction=(math.sin(time.monotonic()*3)+1)/2
            for tag,(x,y,width) in self._progress_tracks.items():
                left=x+width*.75*fraction
                self.panel.coords(tag,left,y,left+width*.25,y)
            if any(i["progress"] == "indeterminate" for i in self.api.items.values()):
                self._progress_tick=self.app.root.after(32,step)
        self._progress_tick=self.app.root.after(32,step)


notifications=NotificationsAPI()


def notify(title, message, id="apkpy_notification", *, channel=DEFAULT_CHANNEL,
           icon="notifications", style="none", picture=None, lines=None,
           actions=None, on_tap=None, on_dismiss=None, ongoing=False,
           progress=None, group=None, when=None):
    """Post/update a persistent notification; Android uses the system drawer."""
    notifications._post(title,message,id,channel=channel,icon=icon,style=style,
        picture=picture,lines=lines,actions=actions,on_tap=on_tap,
        on_dismiss=on_dismiss,ongoing=ongoing,progress=progress,group=group,when=when)
