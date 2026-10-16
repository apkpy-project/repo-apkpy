"""Embedded camera simulator: synthetic scene only, never a webcam."""
import os
import queue
import tempfile
import threading
from pathlib import Path
from ..ui import ComponentDef, _set_backdrop
from ..core.features.camera_view import validate
from .camera import CameraSimulator, CameraAPI
from ..core.features.camera import validate as camera_options


class CameraViewComponent(ComponentDef):
    def _call(self, method, *args):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('camera_view must be controlled from the UI thread')
        session=getattr(self,'_camera_session',None)
        if session is None:
            if method in ('start','stop'):
                self.kwargs['camera_options']['autostart']=method=='start'
                return
            error=self.kwargs.get('on_error')
            if error:error('camera_not_ready')
            if method=='capture' and self.kwargs.get('on_capture'):self.kwargs['on_capture'](False,'')
            return
        getattr(session,method)(*args)
    def capture(self): self._call('capture')
    def start(self): self._call('start')
    def stop(self): self._call('stop')
    def flip(self): self._call('flip')
    def set_zoom(self,value):
        validate({'zoom':value});self._call('set_zoom',value)
    def set_flash(self,value):
        validate({'flash':value});self._call('set_flash',value)
    def set_torch(self,value):
        if not isinstance(value,bool):raise ValueError('set_torch expects True or False')
        self._call('set_torch',value)


def camera_view(id=None,screen=None,parent=None,*,lens='back',flash='off',zoom=1.0,
                mirror=True,fit='cover',aspect_ratio='4:3',autostart=True,
                on_ready=None,on_capture=None,on_error=None):
    """Inline photo visor. Use ordinary buttons to call capture/start/stop/flip.

    on_capture(success, path) receives a private file, without built-in review.
    Android uses CameraX; desktop uses a labelled synthetic scene.
    """
    opts=validate(dict(lens=lens,flash=flash,zoom=zoom,mirror=mirror,fit=fit,
                       aspect_ratio=aspect_ratio,autostart=autostart))
    for cb in (on_ready,on_capture,on_error):
        if cb is not None and not callable(cb):raise ValueError('camera_view callbacks must be callable')
    comp=CameraViewComponent('camera_view',comp_id=id,camera_options=opts,
                             on_ready=on_ready,on_capture=on_capture,on_error=on_error)
    if parent is not None:parent.children.append(comp)
    elif screen is not None:screen._add(comp)
    else:raise ValueError('camera_view requires screen= or parent=')
    return comp


class EmbeddedSimulator:
    def __init__(self,comp,canvas):
        self.comp,self.canvas=comp,canvas
        self.options=dict(comp.kwargs['camera_options'])
        self.scene=CameraSimulator(None,CameraAPI(),camera_options({k:v for k,v in self.options.items() if k not in ('fit','autostart')}),None,None)
        self.wanted=self.options['autostart'];self.ready=False;self.busy=False
        self.revision=0;self.closed=threading.Event();self.queue=queue.Queue();self.photo=None;self.lock=threading.Lock()
        canvas.bind('<Configure>',self.draw)
        canvas.bind('<Map>',self.mapped)
        canvas.bind('<Unmap>',self.unmapped)
        canvas.bind('<Destroy>',self.destroy)
        canvas.bind('<Button-1>',self.focus)
        canvas.after(50,self.poll)
    def callback(self,key,*args):
        fn=self.comp.kwargs.get(key)
        if fn:fn(*args)
    def mapped(self,event=None):
        if self.wanted:self.start()
        else:self.draw()
    def unmapped(self,event=None):
        self.revision+=1;self.ready=False;self.busy=False
    def destroy(self,event=None):
        with self.lock:
            self.closed.set();self.revision+=1
            while not self.queue.empty():
                _,path,_=self.queue.get_nowait()
                if path:Path(path).unlink(missing_ok=True)
    def start(self):
        if self.closed.is_set():return
        self.wanted=True
        if not self.canvas.winfo_ismapped():return
        was=self.ready;self.ready=True;self.draw()
        if not was:self.callback('on_ready')
    def stop(self):
        self.wanted=False;self.unmapped();self.draw()
    def fail(self,reason,capture=False):
        self.callback('on_error',reason)
        if capture:self.callback('on_capture',False,'')
    def flip(self):
        if self.busy:self.fail('camera_busy');return
        self.scene.options['lens']='front' if self.scene.options['lens']=='back' else 'back'
        self.scene.options['zoom']=1;self.scene.torch=False;self.draw()
        if self.ready:self.callback('on_ready')
    def set_zoom(self,value):self.scene.options['zoom']=min(8,value);self.draw()
    def set_flash(self,value):self.scene.options['flash']=value;self.draw()
    def set_torch(self,value):
        if not self.ready:self.fail('camera_not_ready');return
        if self.scene.options['lens']=='front':self.fail('torch_unavailable');return
        self.scene.torch=value;self.draw()
    def focus(self,event):
        if self.ready:
            self.draw();self.canvas.create_rectangle(event.x-18,event.y-18,event.x+18,event.y+18,outline='#95edc7',width=2)
    def draw(self,event=None):
        if self.closed.is_set():return
        from PIL import ImageTk,ImageOps
        c=self.canvas;w=max(1,c.winfo_width());h=max(1,c.winfo_height());c.delete('all')
        if self.ready:
            # Drawn at the size it is shown and smoothed: a 640px scene blown
            # up to a full screen was a staircase of pixels.
            ratio=4/3 if self.options['aspect_ratio']=='4:3' else 16/9
            if self.options['fit']=='cover':sw=max(w,int(h*ratio)+1)
            else:sw=min(w,int(h*ratio))
            sw=max(64,min(sw,1600));sh=max(48,int(sw/ratio))
            im=self.scene.sample(sw,sh,supersample=2)
            im=ImageOps.fit(im,(w,h)) if self.options['fit']=='cover' else ImageOps.contain(im,(w,h))
            self.photo=ImageTk.PhotoImage(im,master=c);c.create_image(w/2,h/2,image=self.photo)
            # What a see-through close button or shutter over it shows:
            # the scene, with the strip drawn on top of it.
            from PIL import Image,ImageDraw
            shown=Image.new('RGB',(w,h),'#000000');shown.paste(im.convert('RGB'),(int(w/2-im.width/2),int(h/2-im.height/2)))
            ImageDraw.Draw(shown).rectangle((0,0,w,30),fill='#101820');_set_backdrop(c,shown)
        else:c.create_text(w/2,h/2,text='Camera paused',fill='#e6eef2',font=('Segoe UI',14))
        c.create_rectangle(0,0,w,30,fill='#101820',outline='')
        c.create_text(w/2,15,text='SIMULATED CAMERA · NO WEBCAM',fill='#95edc7',font=('Segoe UI',9),width=max(1,w-16))
    def capture(self):
        if self.busy:self.fail('camera_busy',True);return
        if not self.ready:self.fail('camera_not_ready',True);return
        self.busy=True;revision=self.revision;opts=dict(self.scene.options)
        def worker():
            path=None;error=None
            try:
                scene=CameraSimulator(None,CameraAPI(),opts,None,None)
                fd,path=tempfile.mkstemp(prefix='apkpy_embedded_',suffix='.jpg');os.close(fd)
                scene.sample(1280,960 if opts['aspect_ratio']=='4:3' else 720).save(path,'JPEG',quality=95)
            except Exception:
                if path:Path(path).unlink(missing_ok=True)
                path=None;error='capture_failed'
            with self.lock:
                if self.closed.is_set():
                    if path:Path(path).unlink(missing_ok=True)
                else:self.queue.put((revision,path,error))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        if self.closed.is_set():return
        while not self.queue.empty():
            revision,path,error=self.queue.get_nowait()
            if revision!=self.revision:
                if path:Path(path).unlink(missing_ok=True)
                continue
            self.busy=False
            if error:self.fail(error,True)
            else:self.callback('on_capture',True,path)
        if not self.closed.is_set():self.canvas.after(50,self.poll)


def render_camera_view(app,comp,parent_widget,is_flex,pack_side,bg_color):
    import tkinter as tk
    import re
    from .. import ui
    style=ui._merge_with_body(comp.kwargs.get('comp_id'),'camera_view')
    mt,mr,mb,ml=ui._parse_margin(style)
    def dimension(key,default):
        raw=style.get(key,'');match=re.fullmatch(r'([0-9.]+)(?:px|dp)?',str(raw).strip())
        return max(48,int(float(match.group(1)))) if match else default
    fluid=str(style.get('width','100%')) in ('100%','match_parent','auto')
    # height: 100% fills the parent, as match_parent does on the phone; it was
    # a 280px strip, so a full-screen viewfinder could not be previewed.
    fluid_height=str(style.get('height','')).strip().lower() in ('100%','match_parent','fill')
    canvas=tk.Canvas(parent_widget,width=dimension('width',320),height=dimension('height',280),bg='#000000',highlightthickness=0,bd=0)
    args=dict(padx=(ml,mr),pady=(mt,mb))
    if is_flex:args['side']=pack_side
    if fluid_height:canvas.pack(fill='both' if fluid else 'y',expand=True,**args)
    else:canvas.pack(fill='x' if fluid else None,**args)
    old=getattr(comp,'_camera_session',None)
    if old:old.destroy()
    comp.widget=canvas;comp._camera_session=EmbeddedSimulator(comp,canvas)
