"""Camera simulator. Synthetic/imported scenes, never implicit webcam access."""
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from ..core.features.camera import OPTIONS, validate
from ..core.features.camera_ui import CONTROLS, LABELS, COLORS, control_rows


class CameraAPI:
    def __init__(self):
        self._session = None

    def available(self):
        """The Previewer has a simulator; Android checks for camera hardware."""
        return True

    def capabilities(self, on_result=None, on_error=None):
        result = {"simulated": True, "available": True,
                  "manual_controls_enabled": True, "raw_capture_enabled": False,
                  "cameras": [{"id": "simulated_"+lens, "lens": lens,
                               "flash": lens == "back", "max_zoom": 8.0,
                               "min_exposure": -4, "max_exposure": 4, "exposure_step": .5,
                               "min_iso": 1, "max_iso": 51200,
                               "min_shutter_ms": 0.001, "max_shutter_ms": 1000,
                               "max_focus_distance": 100,
                               "white_balance_modes": ["auto", "daylight", "cloudy", "incandescent", "fluorescent"],
                               "hardware_manual_sensor": False, "hardware_raw": False}
                              for lens in ("back", "front")]}
        if on_result:
            on_result(result)
        return result

    def capture(self, on_result=None, *, on_error=None, **options):
        if "mode" in options:
            raise ValueError("capture always takes a photo; use camera.open(mode=...)")
        return self.open(on_result, on_error=on_error, mode="photo", **options)

    def record(self, on_result=None, *, on_error=None, **options):
        if "mode" in options:
            raise ValueError("record always takes video; use camera.open(mode=...)")
        return self.open(on_result, on_error=on_error, mode="video", **options)

    def open(self, on_result=None, *, on_error=None, mode="photo", lens="back",
             flash="off", quality="fhd", aspect_ratio="4:3", zoom=1.0, exposure=0,
             timer=0, grid=True, audio=True, mirror=True, max_duration=60, jpeg_quality=95,
             iso=0, shutter_ms=0.0, focus_distance=-1.0, white_balance="auto",
             controls=None, labels=None, colors=None, title="CAMERA", button_radius=18,
             controls_position="auto"):
        opts = validate({k: v for k, v in locals().copy().items() if k in OPTIONS})
        if bool(opts['iso']) != bool(opts['shutter_ms']):
            raise ValueError("Set both iso and shutter_ms, or leave both at 0 for auto exposure")
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Open the camera from a visible screen callback, not a background worker")
        from .. import ui
        def answer(reason):
            if on_error:
                on_error(reason)
            if on_result:
                on_result(False, "")
        if self._session is not None:
            answer("busy")
            return
        app = ui.live_preview()
        if app is None:
            answer("unavailable")
            return
        self._session = CameraSimulator(app, self, opts, on_result, on_error)
        self._session.open()


class CameraSimulator:
    BG = "#0e1216"
    PANEL = "#1a2026"
    ACCENT = "#95edc7"
    MUTED = "#9caebd"

    def __init__(self, app, api, options, on_result, on_error):
        self.app, self.api, self.options = app, api, dict(options)
        palette = dict(COLORS, **(options.get("colors") or {}))
        self.BG, self.PANEL, self.ACCENT = (palette[k] for k in ("background", "surface", "accent"))
        self.TEXT, self.MUTED, self.ON_ACCENT = (palette[k] for k in ("text", "muted", "on_accent"))
        self.labels = dict(LABELS, **(options.get("labels") or {}))
        self.order = list(CONTROLS if options.get("controls") is None else options["controls"])
        self.on_result, self.on_error = on_result, on_error
        self.canvas = None
        self.scene = 0
        self.imported = None
        self.focus = None
        self.torch = False
        self.pending = None
        self.recording = False
        self.paused = False
        self.review = False
        self.closed = False
        self.busy = False
        self.countdown = 0
        self.message = "Tap the viewfinder to focus"
        self.frames = 0
        self._stop = threading.Event()
        self._worker = None
        self._tick = None
        self._record_error = None
        self.controls = {}
        self.photo = None
        self._zoom_drag = False
        self._exposure_drag = False
        self._escape = None

    def open(self):
        import tkinter as tk
        self.canvas = tk.Canvas(self.app.root, bg=self.BG, highlightthickness=0)
        self.canvas.place(x=0, y=24, relwidth=1, relheight=1, height=-24)
        self.canvas.tk.call("raise", self.canvas._w)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<Button-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Destroy>", self.destroyed)
        self.canvas.bind("<MouseWheel>", self.scroll)
        self._escape = self.app.root.bind("<Escape>", lambda e: self.cancel(), add="+")
        self.draw()

    def font(self, size, bold=False):
        return ("Segoe UI", -size, "bold" if bold else "normal")

    def text(self, x, y, text, size=13, color=None, width=None, anchor="center", bold=False):
        return self.canvas.create_text(x,y,text=text,font=self.font(size,bold),fill=color or self.TEXT,
                                       width=width or 0,anchor=anchor,justify="center")

    def control(self, name, rect, label, command, selected=False, enabled=True):
        from .. import ui
        x,y,w,h=rect
        self.controls[name]=(rect,command if enabled else None)
        ui._create_rounded_rect(self.canvas,x,y,x+w,y+h,min(self.options["button_radius"],h/2),fill=self.ACCENT if selected else self.PANEL,outline="")
        self.text(x+w/2,y+h/2,label,12,self.ON_ACCENT if selected else self.TEXT if enabled else self.MUTED,w-12,bold=True)

    def control_label(self, key):
        if key == "shutter":
            key = "stop" if self.recording else "record" if self.options["mode"] == "video" else "capture"
        elif key == "pause":
            key = "resume" if self.paused else "pause"
        value = None
        if key == "timer": value = str(self.options[key]) + "s"
        elif key in ("flash", "mode", "quality"): value = self.options[key]
        elif key == "ratio": value = self.options["aspect_ratio"]
        elif key in ("grid", "audio"): value = "on" if self.options[key] else "off"
        elif key == "torch": value = "on" if self.torch else "off"
        return self.labels[key] + (" " + str(value) if value is not None else "")

    def measured_height(self, text, width, size=12, bold=True):
        item = self.text(0, 0, text, size, width=max(1, width), bold=bold)
        bounds = self.canvas.bbox(item)
        self.canvas.delete(item)
        return bounds[3] - bounds[1] if bounds else size

    def sample(self, width=960, height=720, supersample=1):
        from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFilter
        if self.imported is not None:
            im=ImageOps.fit(self.imported,(width,height))
        elif supersample>1:
            # The viewfinder: the scene drawn larger and scaled down, so its
            # circle and lines are smooth at the size they are shown.
            im=self.sample(int(width*supersample),int(height*supersample)).resize((width,height),Image.LANCZOS)
            return im
        else:
            palettes=[("#233f50","#95edc7","#e2b77f"),("#412e48","#eda5bc","#ddc2ef"),("#2e4037","#e7eabe","#a1ced9")]
            bg,accent,soft=palettes[self.scene%len(palettes)]
            im=Image.new("RGB",(width,height),bg);d=ImageDraw.Draw(im)
            # Deliberately a calibration scene, not a fake photo from a webcam.
            for n in range(14):
                y=int(height*n/14);d.line((0,y,width,height*.35+y*.65),fill=soft,width=1)
            d.rounded_rectangle((width*.16,height*.24,width*.62,height*.71),radius=width*.04,fill=accent)
            d.ellipse((width*.49,height*.13,width*.83,height*.57),fill=soft)
            d.polygon((width*.54,height*.86,width*.85,height*.54,width*.91,height*.88),fill="#0e1822")
            d.rectangle((0,height*.91,width,height),fill="#0c1820")
            d.text((width*.035,height*.94),"APKPY / CAMERA TEST SCENE",fill="white")
        zoom=min(8,max(1,float(self.options["zoom"])))
        if zoom>1:
            w,h=im.size;cw,ch=w/zoom,h/zoom;im=im.crop(((w-cw)/2,(h-ch)/2,(w+cw)/2,(h+ch)/2)).resize((width,height))
        if self.options["lens"]=="front" and self.options["mirror"]:
            im=ImageOps.mirror(im)
        brightness=2**(self.options["exposure"]*.25)*(1.15 if self.torch else 1)
        if self.options.get('iso') and self.options.get('shutter_ms'):
            brightness=self.options['iso']/200*self.options['shutter_ms']/10
        im=ImageEnhance.Brightness(im).enhance(brightness)
        wb=self.options.get('white_balance','auto')
        multipliers={'daylight':(1.04,1,.96),'cloudy':(1.1,1,.88),'incandescent':(.85,1,1.15),'fluorescent':(1.03,.96,1.05)}
        if wb in multipliers:
            im=Image.merge('RGB',tuple(channel.point(lambda p,m=m:p*m) for channel,m in zip(im.split(),multipliers[wb])))
        focus=self.options.get('focus_distance',-1)
        if focus>=0:im=im.filter(ImageFilter.GaussianBlur(min(5,abs(focus-2)*.7)))
        return im

    def draw(self):
        if self.closed or self.canvas is None:
            return
        from PIL import ImageTk, ImageOps, Image
        c=self.canvas;w=max(280,c.winfo_width());h=max(200,c.winfo_height())
        c.delete("all");self.controls={}
        self.zoom_rect=self.exposure_rect=None
        wide=w>h*1.15 and self.options["controls_position"]=="auto"
        panel_x=w-300 if wide else 0;panel_w=300 if wide else w
        pw=panel_w-28
        rows=control_rows(self.order,self.options["mode"])
        heights=[]
        for row in rows:
            if row[0] in ("zoom","exposure"):
                heights.append(40)
            else:
                cw=(pw-8*(len(row)-1))/len(row)
                heights.append(max(48,max(self.measured_height(self.control_label(k),cw-12)+16 for k in row))+8)
        panel_height=(220 if self.review else sum(heights)+76)
        header_height=max(64, max(self.measured_height(self.labels[k],64,12) for k in ("close","pro"))+28,
                          self.measured_height(self.options["title"],max(1,w-180),14)+40)
        logical_height=max(h,header_height+panel_height+110) if not wide else max(h,header_height+panel_height+12)
        c.configure(scrollregion=(0,0,w,logical_height))
        top_panel=self.options["controls_position"]=="top" and not wide
        top=header_height+(panel_height if top_panel else 0)
        bottom=logical_height-12 if wide or top_panel else logical_height-panel_height
        vx=12;vw=w-324 if wide else w-24;vh=max(100,bottom-top)
        self.viewport=(vx,top,vw,vh)
        self.control("close",(12,10,76,header_height-24),self.labels["close"],self.cancel)
        self.text(w/2,header_height/2-10,self.options["title"],14,self.ACCENT,w-180,bold=True)
        self.text(w/2,header_height-6,"PREVIEW SIMULATOR · NO CAMERA ACCESS",9,self.MUTED,w-24)
        if "pro" in self.order:
            self.control("pro",(w-88,10,76,header_height-24),self.labels["pro"],self.fail_menu,enabled=not (self.busy or self.recording or self.review))
        if self.review and self.pending and self.pending.suffix==".jpg":
            with Image.open(self.pending) as original: im=original.copy()
        else:
            im=self.sample(640,480 if self.options["aspect_ratio"]=="4:3" else 360)
        im=ImageOps.contain(im,(max(1,int(vw)),max(1,int(vh))))
        self.photo=ImageTk.PhotoImage(im,master=c)
        c.create_rectangle(vx,top,vx+vw,top+vh,fill="#000000",outline="")
        c.create_image(vx+vw/2,top+vh/2,image=self.photo)
        if self.options["grid"] and not self.review:
            for n in (1,2):
                c.create_line(vx+vw*n/3,top,vx+vw*n/3,top+vh,fill="#5e7778")
                c.create_line(vx,top+vh*n/3,vx+vw,top+vh*n/3,fill="#5e7778")
        if self.focus and not self.review:
            fx,fy=self.focus;c.create_rectangle(fx-23,fy-23,fx+23,fy+23,outline=self.ACCENT,width=2)
        if self.countdown:
            self.text(vx+vw/2,top+vh/2,str(self.countdown),60,self.ACCENT,bold=True)
        if self.recording:
            self.text(vx+vw/2,top+24,("PAUSED" if self.paused else "● REC")+"  %02d:%02d"%(self.frames//12//60,self.frames//12%60),16,"#ff9f99",bold=True)
        y=header_height+8 if wide or top_panel else bottom+8;x=panel_x+14
        if self.review:
            self.text(panel_x+panel_w/2,y+20,"Review your "+("photo" if self.pending.suffix==".jpg" else "video"),18,bold=True)
            self.text(panel_x+panel_w/2,y+54,"Real file · simulated scene"+(" · silent MP4" if self.pending.suffix==".mp4" else ""),12,self.MUTED,pw)
            self.control("retake",(x,y+90,(pw-10)/2,64),self.labels["retake"],self.retake)
            self.control("use",(x+(pw+10)/2,y+90,(pw-10)/2,64),self.labels["use_photo" if self.pending.suffix==".jpg" else "use_video"],self.accept,True)
            if self.pending.suffix==".mp4":
                self.control("play",(x,y+165,pw,44),"Play saved video",self.play)
            return
        self.text(panel_x+panel_w/2,y+8,self.message,12,self.ACCENT,pw)
        y+=30;locked=self.busy or self.recording or bool(self.countdown)
        actions={"flash":lambda:self.cycle("flash",("off","on","auto")),
                 "timer":lambda:self.cycle("timer",(0,3,5,10)),"grid":lambda:self.toggle("grid"),
                 "quality":lambda:self.cycle("quality",("sd","hd","fhd","uhd")),
                 "ratio":lambda:self.cycle("aspect_ratio",("4:3","16:9")),"torch":self.toggle_torch,
                 "flip":lambda:self.cycle("lens",("back","front")),"shutter":self.shutter,
                 "pause":self.toggle_pause,"mode":lambda:self.cycle("mode",("photo","video")),
                 "audio":lambda:self.toggle("audio")}
        for row,height in zip(rows,heights):
            if row[0] in ("zoom","exposure"):
                key=row[0];value="%.1f×"%self.options["zoom"] if key=="zoom" else "%+.1f"%(self.options["exposure"]*.5)
                self.text(x,y+8,self.labels[key],10,self.MUTED,width=pw-62,anchor="w")
                self.text(x+pw,y+8,value,11,self.ACCENT,anchor="e")
                rect=(x+6,y+27,pw-12,18);setattr(self,key+"_rect",rect)
                self.slider(rect,(min(8,self.options["zoom"])-1)/7 if key=="zoom" else (max(-4,min(4,self.options["exposure"]))+4)/8)
            else:
                cw=(pw-8*(len(row)-1))/len(row)
                for i,key in enumerate(row):
                    enabled=not locked
                    if key=="shutter":enabled=not self.busy and not self.countdown
                    elif key=="pause":enabled=self.recording and not self.busy
                    elif key=="quality":enabled=enabled and self.options["mode"]=="video"
                    elif key=="flash":enabled=enabled and self.options["mode"]=="photo" and self.options["lens"]=="back" and not self.options["iso"]
                    self.control(key,(x+i*(cw+8),y,cw,height-8),self.control_label(key),actions[key],key=="shutter",enabled)
            y+=height
        y+=14
        self.text(panel_x+panel_w/2,y,"Video simulation: 640px · 12 fps · no audio" if self.options["mode"]=="video" else "Synthetic scene · focus and flash are simulated",10,self.MUTED,pw)

    def slider(self, rect, progress):
        x,y,w,h=rect;self.canvas.create_line(x,y,x+w,y,fill="#384950",width=4)
        self.canvas.create_line(x,y,x+w*progress,y,fill=self.ACCENT,width=4)
        px=x+w*progress;self.canvas.create_oval(px-6,y-6,px+6,y+6,fill=self.ACCENT,outline="")

    def press(self, e):
        from types import SimpleNamespace
        e=SimpleNamespace(x=e.x,y=self.canvas.canvasy(e.y))
        for rect,fn in self.controls.values():
            x,y,w,h=rect
            if x<=e.x<=x+w and y<=e.y<=y+h:
                if fn: fn()
                return
        if self.review or self.busy or self.countdown:
            return
        for attr,rect in (("_zoom_drag",self.zoom_rect),("_exposure_drag",self.exposure_rect)):
            if rect is None:continue
            x,y,w,h=rect
            if x-10<=e.x<=x+w+10 and abs(e.y-y)<=14:
                setattr(self,attr,True);self.drag(e);return
        x,y,w,h=self.viewport
        if x<=e.x<=x+w and y<=e.y<=y+h:
            self.options['focus_distance']=-1
            self.focus=(e.x,e.y);self.message="Focus point set (simulated)";self.draw()

    def drag(self,e):
        if self._zoom_drag:
            x,y,w,h=self.zoom_rect;self.options["zoom"]=1+7*max(0,min(1,(e.x-x)/w));self.draw()
        elif self._exposure_drag:
            x,y,w,h=self.exposure_rect;self.options["exposure"]=round(-4+8*max(0,min(1,(e.x-x)/w)));self.draw()

    def release(self,e):
        self._zoom_drag=self._exposure_drag=False

    def scroll(self, e):
        self.canvas.yview_scroll(-1 if e.delta>0 else 1,"units")
        return "break"

    def cycle(self,key,choices):
        old=self.options[key];self.options[key]=choices[(choices.index(old)+1)%len(choices)] if old in choices else choices[0]
        if key=="lens": self.torch=False
        self.message=self.options["lens"].title()+" lens · "+self.options["mode"]
        self.draw()

    def toggle(self,key):
        self.options[key]=not self.options[key];self.draw()

    def toggle_torch(self):
        if self.options["lens"]=="front": self.message="No torch on the simulated front lens"
        else: self.torch=not self.torch
        self.draw()

    def next_scene(self):
        if self.busy or self.countdown:return
        self.imported=None;self.scene+=1;self.draw()

    def toggle_pause(self):
        if self.recording:self.paused=not self.paused;self.draw()

    def load_image(self):
        from tkinter import filedialog
        from PIL import Image, ImageOps
        path=filedialog.askopenfilename(parent=self.app.root,title="Use image as the camera scene",filetypes=[("Images","*.png *.jpg *.jpeg *.webp")])
        if path:
            try:
                with Image.open(path) as im:
                    im=ImageOps.exif_transpose(im);im.thumbnail((1920,1920));self.imported=im.convert("RGB")
                self.message="Imported scene · original file stays unchanged"
            except Exception:self.message="Could not read that image"
            self.draw()

    def fail_menu(self):
        import tkinter as tk
        menu=tk.Menu(self.canvas,tearoff=False)
        def manual(iso,ms):
            self.options['iso']=iso;self.options['shutter_ms']=ms;self.message='Auto exposure' if not iso else 'ISO %d · %.1f ms (simulated)'%(iso,ms);self.draw()
        menu.add_command(label="Auto exposure",command=lambda:manual(0,0))
        for iso,ms in ((100,10),(200,10),(400,5),(800,10)):
            menu.add_command(label="ISO %d · %.1f ms (simulated)"%(iso,ms),command=lambda i=iso,t=ms:manual(i,t))
        wb=tk.Menu(menu,tearoff=False)
        for value in ('auto','daylight','cloudy','incandescent','fluorescent'):
            wb.add_command(label=value.title(),command=lambda v=value:self.set_pro('white_balance',v))
        menu.add_cascade(label='White balance',menu=wb)
        focus=tk.Menu(menu,tearoff=False)
        for name,value in (('Autofocus',-1),('Infinity',0),('2 diopters',2),('5 diopters',5)):
            focus.add_command(label=name,command=lambda v=value:self.set_pro('focus_distance',v))
        menu.add_cascade(label='Focus (simulated)',menu=focus)
        menu.add_separator()
        menu.add_command(label="Change simulated scene",command=self.next_scene)
        menu.add_command(label="Import scene image",command=self.load_image)
        for title,reason in (("Simulate permission denied","permission_denied"),("Simulate camera busy","camera_unavailable"),("Simulate storage error","storage_unavailable")):
            menu.add_command(label=title,command=lambda r=reason:self.finish(False,"",r))
        menu.add_separator();menu.add_command(label="Focus, flash and lens changes are simulated",state="disabled")
        menu.tk_popup(self.canvas.winfo_rootx()+max(0,self.canvas.winfo_width()-250),self.canvas.winfo_rooty()+55)

    def set_pro(self,key,value):
        self.options[key]=value;self.message=key.replace('_',' ').title()+': '+str(value)+' (simulated)';self.draw()

    def shutter(self):
        if self.recording:
            self.busy=True;self._stop.set();self.message="Finalizing MP4…";self.draw();return
        if self.busy or self.countdown:return
        self.countdown=self.options["timer"]
        self.count()

    def count(self):
        if self.closed:return
        if self.countdown:
            self.draw();self._tick=self.app.root.after(1000,self.count_next)
        elif self.options["mode"]=="photo":self.take_photo()
        else:self.start_video()

    def count_next(self):
        self.countdown=max(0,self.countdown-1);self.count()

    def new_file(self,suffix):
        folder=Path(tempfile.gettempdir())/"apkpy_camera";folder.mkdir(exist_ok=True)
        fd,name=tempfile.mkstemp(prefix="capture_",suffix=suffix,dir=str(folder));os.close(fd)
        self.pending=Path(name)
        return self.pending

    def take_photo(self):
        try:
            self.new_file(".jpg");self.sample(1280,960 if self.options["aspect_ratio"]=="4:3" else 720).save(self.pending,quality=self.options["jpeg_quality"])
            self.review=True;self.focus=None;self.draw()
        except Exception as exc:self.finish(False,"","storage_unavailable: "+str(exc))

    def start_video(self):
        try:
            import cv2
            self.new_file(".mp4");height=480 if self.options["aspect_ratio"]=="4:3" else 360
            writer=cv2.VideoWriter(str(self.pending),cv2.VideoWriter_fourcc(*"mp4v"),12,(640,height))
            if not writer.isOpened():raise RuntimeError("MP4 encoder is unavailable")
        except Exception as exc:self.finish(False,"","video_unavailable: "+str(exc));return
        self.recording=True;self.paused=False;self.frames=0;self._stop.clear();self._record_error=None
        def encode():
            import numpy as np
            try:
                while not self._stop.is_set():
                    start=time.monotonic()
                    if not self.paused:
                        frame=self.sample(640,height)
                        # A moving marker makes pause/resume inspectable in the saved clip.
                        from PIL import ImageDraw
                        ImageDraw.Draw(frame).ellipse((self.frames*5%600,20,self.frames*5%600+24,44),fill="#ff6f72")
                        writer.write(cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2BGR));self.frames+=1
                        if self.frames>=self.options["max_duration"]*12:self._stop.set()
                    self._stop.wait(max(0,1/12-(time.monotonic()-start)))
            except Exception as exc:self._record_error=str(exc)
            finally:
                writer.release()
                if self.closed:
                    self.discard()
        self._worker=threading.Thread(target=encode,name="apkpy-camera-video",daemon=True);self._worker.start();self.video_tick()

    def video_tick(self):
        if self.closed:return
        if self._worker and not self._worker.is_alive():
            self.recording=False;self.busy=False
            if self._record_error or not self.pending or self.pending.stat().st_size<100:
                self.finish(False,"","recording_failed");return
            self.review=True
        self.draw()
        if self.recording:self._tick=self.app.root.after(100,self.video_tick)

    def play(self):
        # Explicit user action opens only the capture the simulator produced.
        if self.pending and self.pending.exists():
            import webbrowser
            webbrowser.open(self.pending.as_uri())

    def discard(self):
        if self.pending:
            self.pending.unlink(missing_ok=True);self.pending=None

    def retake(self):
        self.discard();self.review=False;self.draw()

    def accept(self):
        if not self.pending or not self.pending.is_file():return
        path=str(self.pending);self.pending=None;self.finish(True,path,"ok")

    def cancel(self):
        self.finish(False,"","cancelled")

    def destroyed(self, event):
        if event.widget is not self.canvas or self.closed:
            return
        # Root/window shutdown is not an interactive cancellation: do not call
        # application callbacks against widgets which are being destroyed.
        self.closed = True
        self._stop.set()
        if self._tick:
            try:
                self.app.root.after_cancel(self._tick)
            except Exception:
                pass
            self._tick = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2)
        if not self._worker or not self._worker.is_alive():
            self.discard()
        self.api._session = None

    def finish(self,success,path,reason):
        if self.closed:return
        self.closed=True;self._stop.set();self.countdown=0
        if self._tick:
            self.app.root.after_cancel(self._tick);self._tick=None
        if self._worker and self._worker.is_alive():self._worker.join(timeout=2)
        if self.pending and (not self._worker or not self._worker.is_alive()):self.discard()
        if self.canvas:self.canvas.destroy();self.canvas=None
        if self._escape:self.app.root.unbind("<Escape>",self._escape)
        self.api._session=None
        if not success and reason!="cancelled" and self.on_error:self.on_error(reason)
        if self.on_result:self.on_result(success,path)


camera=CameraAPI()
