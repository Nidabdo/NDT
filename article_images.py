"""Images intégrées aux procédures, collage et poignées de redimensionnement."""
import base64
import io
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageOps, ImageTk, ImageGrab

LIMIT=30*1024*1024


def decode_image(data):
    if not isinstance(data,str) or len(data)>LIMIT*4//3+8:
        raise ValueError('Image trop volumineuse (30 Mo maximum).')
    try:
        with Image.open(io.BytesIO(base64.b64decode(data,validate=True))) as source:
            if source.width*source.height>25_000_000:raise ValueError('Image trop grande.')
            return ImageOps.exif_transpose(source).convert('RGBA')
    except (OSError,Image.DecompressionBombError) as error:
        raise ValueError('Image illisible.') from error


def encode_image(source,name='Image collée'):
    if source.width*source.height>25_000_000:raise ValueError('Image trop grande.')
    source=ImageOps.exif_transpose(source).convert('RGBA')
    output=io.BytesIO();source.save(output,format='PNG')
    if output.tell()>LIMIT:raise ValueError('Image trop volumineuse (30 Mo maximum).')
    return dict(name=name,data=base64.b64encode(output.getvalue()).decode('ascii'),width=max(30,min(640,source.width)),offset=0)


def import_image(path):
    path=Path(path)
    if path.stat().st_size>LIMIT:raise ValueError('Image trop volumineuse (30 Mo maximum).')
    return encode_image(decode_image(base64.b64encode(path.read_bytes()).decode('ascii')),path.name)


def validate_images(article):
    images=article.get('images',[])
    if not isinstance(images,list):raise ValueError('Images invalides.')
    for item in images:
        if (not isinstance(item,dict) or not isinstance(item.get('name'),str)
                or type(item.get('width')) is not int or not 30<=item['width']<=4000
                or type(item.get('offset')) is not int or not 0<=item['offset']<=len(article['content'])):
            raise ValueError('Image invalide.')
        decode_image(item.get('data'))


class ImageDocument:
    def __init__(self,text,editable=False):
        self.text=text;self.editable=editable;self.items={};self.selected=None;self.drag=None;self.pending=None
        text.bind('<Configure>',self.schedule,add='+')
        text.bind('<Destroy>',self.dispose,add='+')
        if editable:
            text.bind('<Button-1>',lambda e:self.select(None),add='+')
            text.bind('<<Modified>>',self.changed,add='+')

    def changed(self,event=None):
        if not self.text.edit_modified():return
        self.text.edit_modified(False)
        active=set(self.text.window_names())
        for name in list(self.items):
            if name not in active:
                if self.selected==name:self.selected=None
                self.items.pop(name)['canvas'].destroy()

    def dispose(self,event):
        if event.widget==self.text and self.pending:
            self.text.after_cancel(self.pending);self.pending=None

    def schedule(self,event=None):
        if self.pending:self.text.after_cancel(self.pending)
        self.pending=self.text.after(50,self.refresh)

    def load(self,content,images=()):
        state=self.text.cget('state');self.text.configure(state='normal')
        for entry in self.items.values():entry['canvas'].destroy()
        self.items.clear();self.selected=None;self.text.delete('1.0','end')
        offset=0
        for item in sorted(images,key=lambda item:item['offset']):
            self.text.insert('end',content[offset:item['offset']]);self.insert(item,'end-1c');offset=item['offset']
        self.text.insert('end',content[offset:]);self.text.configure(state=state)

    def insert(self,item,index='insert'):
        source=decode_image(item['data'])
        canvas=tk.Canvas(self.text,highlightthickness=0,borderwidth=0,takefocus=self.editable)
        name=str(canvas)
        self.items[name]=dict(item=dict(item),source=source,canvas=canvas,size=None)
        self.text.window_create(index,window=canvas,pady=6,align='center')
        if self.editable:
            canvas.bind('<Button-1>',lambda e,n=name:self.press(n,e))
            canvas.bind('<B1-Motion>',self.motion)
            canvas.bind('<ButtonRelease-1>',self.release)
            canvas.bind('<Motion>',lambda e,n=name:self.hover(n,e))
            canvas.bind('<Delete>',lambda e:self.remove_image())
            canvas.bind('<Escape>',lambda e:self.select(None))
            if hasattr(self,'paste'):canvas.bind('<<Paste>>',self.paste)
        self.draw(name)
        return name

    def draw(self,name):
        entry=self.items[name];canvas=entry['canvas'];source=entry['source']
        available=self.text.winfo_width()-2*int(self.text.cget('padx'))-20
        width=min(entry['item']['width'],max(30,available if available>0 else 320))
        size=(width,max(1,round(width*source.height/source.width)))
        if entry['size']!=size:
            entry['photo']=ImageTk.PhotoImage(source.resize(size,Image.Resampling.LANCZOS),master=self.text);entry['size']=size
        w,h=size;canvas.configure(width=w+12,height=h+12,bg=self.text.cget('background'))
        canvas.delete('all');canvas.create_image(6,6,anchor='nw',image=entry['photo'])
        if self.editable and self.selected==name:
            canvas.create_rectangle(6,6,w+6,h+6,outline='#72dfcd',width=2)
            for x,y in ((6,6),(w+6,6),(6,h+6),(w+6,h+6)):
                canvas.create_rectangle(x-5,y-5,x+5,y+5,fill='#72dfcd',outline='#0d1724')

    def refresh(self):
        self.pending=None
        for kind,name,index in self.text.dump('1.0','end',window=True):
            if name in self.items:self.draw(name)

    def serialize(self):
        parts=[];images=[];offset=0
        for kind,value,index in self.text.dump('1.0','end-1c',text=True,window=True):
            if kind=='text':parts.append(value);offset+=len(value)
            elif value in self.items:images.append(dict(self.items[value]['item'],offset=offset))
        return ''.join(parts),images

    def select(self,name):
        previous=self.selected;self.selected=name
        for key in (previous,name):
            if key in self.items:self.draw(key)

    def corner(self,name,event):
        w,h=self.items[name]['size']
        for sx,sy,x,y in ((-1,-1,6,6),(1,-1,w+6,6),(-1,1,6,h+6),(1,1,w+6,h+6)):
            if abs(event.x-x)<=10 and abs(event.y-y)<=10:return sx,sy

    def hover(self,name,event):
        corner=self.corner(name,event) if self.selected==name else None
        self.items[name]['canvas'].configure(cursor=('size_nw_se' if corner[0]==corner[1] else 'size_ne_sw') if corner else 'hand2')

    def press(self,name,event):
        self.select(name);entry=self.items[name];entry['canvas'].focus_set()
        self.text.mark_set('insert',self.text.index(name)+'+1c')
        corner=self.corner(name,event)
        if corner:
            self.drag=(name,corner,event.x_root,event.y_root,entry['size'][0])
            entry['canvas'].grab_set()
        return 'break'

    def motion(self,event):
        if not self.drag:return
        name,(sx,sy),x,y,width=self.drag
        source=self.items[name]['source'];ratio=source.height/source.width
        dx=(event.x_root-x)*sx;dy=(event.y_root-y)*sy
        delta=(dx+ratio*dy)/(1+ratio*ratio)
        available=max(30,self.text.winfo_width()-2*int(self.text.cget('padx'))-20)
        self.items[name]['item']['width']=max(30,min(4000,available,round(width+delta)))
        self.draw(name)
        return 'break'

    def release(self,event=None):
        if self.drag:
            self.items[self.drag[0]]['canvas'].grab_release();self.drag=None
            # Restore the article dialog's modal grab after the pointer drag.
            self.text.winfo_toplevel().grab_set()
        return 'break'

    def remove_image(self):
        if self.selected:
            name=self.selected;self.text.delete(name);self.items.pop(name)['canvas'].destroy();self.selected=None
        return 'break'


class ArticleImageEditor(ImageDocument):
    def __init__(self,text,toolbar,app,window):
        super().__init__(text,editable=True)
        self.app=app;self.window=window
        ttk.Button(toolbar,text='+ Insérer une image',command=self.add_image).pack(side='left')
        ttk.Button(toolbar,text='Coller',command=self.paste).pack(side='left',padx=6)
        ttk.Button(toolbar,text='Retirer l’image',command=self.remove_image).pack(side='right')
        text.bind('<<Paste>>',self.paste)
        self.menu=tk.Menu(text,tearoff=False)
        self.menu.add_command(label='Coller (Ctrl+V)',command=self.paste)
        text.bind('<Button-3>',lambda e:self.menu.tk_popup(e.x_root,e.y_root))

    def add_image(self,path=None):
        if path is None:path=filedialog.askopenfilename(parent=self.window,title='Insérer une image',filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp *.gif')])
        if not path:return
        try:self.insert_selected(import_image(path))
        except (OSError,ValueError) as error:self.app.error('Image non importée',str(error))

    def insert_selected(self,item):
        if self.text.tag_ranges('sel'):self.text.delete('sel.first','sel.last')
        self.select(self.insert(item));self.text.see(self.selected);self.text.focus_set()

    def paste(self,event=None):
        try:
            data=ImageGrab.grabclipboard()
            if isinstance(data,Image.Image):
                self.insert_selected(encode_image(data));return 'break'
            if isinstance(data,list):
                images=[import_image(path) for path in data if Path(path).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.bmp','.gif')]
                if images:
                    for item in images:self.insert_selected(item)
                    return 'break'
        except (OSError,ValueError) as error:
            self.app.error('Collage impossible',str(error));return 'break'
        # Keep ordinary text paste working, including selection replacement.
        try:value=self.text.clipboard_get()
        except tk.TclError:return 'break'
        if self.text.tag_ranges('sel'):self.text.delete('sel.first','sel.last')
        self.text.insert('insert',value);self.text.see('insert')
        return 'break'
