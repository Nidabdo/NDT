"""Formulaire du parcours choisi et surfaces arrondies."""
import tkinter as tk
import math
from tkinter import ttk


def visible_path(questions, answers, resolve, skipped=()):
    path=[]
    current=0 if questions else None
    while current is not None:
        path.append(current)
        q=questions[current]
        value=answers.get(current)
        if q['type']=='choice' and value is None and current not in skipped:
            possible={resolve(questions,current,i,path) for i in range(len(q['choices']))}
            if not q.get('required',True):possible.add(resolve(questions,current,None,path))
            if len(possible)>1:break
            current=next(iter(possible),None)
        else:
            current=resolve(questions,current,value,path)
    return path


def style_rounded_button(app,name,bg,hover,indicator=None):
    if not hasattr(app,'button_images'):app.button_images={}
    element=name.replace('.','')+'.rounded'
    images=app.button_images.get(name)
    if images is None:
        images=[tk.PhotoImage(master=app,width=40,height=40) for _ in range(3)]
        app.button_images[name]=images
        app.style.element_create(element,'image',images[0],('pressed',images[1]),('active',images[1]),('focus',images[2]),border=16,padding=0,sticky='nsew')
        app.style.layout(name,[(element,{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
    for index,(image,color) in enumerate(zip(images,[bg,hover,bg])):
        image.blank()
        radius=8 if name.startswith(('Sidebar.','Nav.')) else 14
        for y in range(40):
            distance=max(0,radius-min(y,39-y)-0.5)
            left=max(0,math.ceil(radius-math.sqrt(max(0,radius*radius-distance*distance))))
            focus_color='#70ddc9' if name.startswith('Sidebar.') else app.p['fg']
            image.put(focus_color if index==2 else color,to=(left,y,40-left,y+1))
            if index==2 and 2<=y<38:
                image.put(color,to=(min(left+2,19),y,max(40-left-2,21),y+1))
            if indicator:
                # Le trait épouse tout le bord gauche, y compris ses deux courbes.
                image.put(indicator,to=(left,y,left+3,y+1))


def rounded(canvas,x,y,w,h,r,**kw):
    r=min(r,w/2,h/2)
    points=[]
    for cx,cy,start in [(x+w-r,y+r,-90),(x+w-r,y+h-r,0),(x+r,y+h-r,90),(x+r,y+r,180)]:
        for step in range(13):
            a=math.radians(start+step*7.5)
            points.extend((cx+r*math.cos(a),cy+r*math.sin(a)))
    return canvas.create_polygon(*points,**kw)


class RoundedPanel(tk.Canvas):
    def __init__(self,parent,app,padding=24,radius=20,surface='surface',body_style='Surface.TFrame',autosize=True,shadow=True,accent_top=False):
        super().__init__(parent,bg=app.p['bg'],highlightthickness=0,width=100,height=160)
        self.app,self.padding=app,padding
        self.radius,self.surface,self.autosize,self.shadow=radius,surface,autosize,shadow
        self.accent_top=accent_top
        self.body=ttk.Frame(self,style=body_style)
        self.window=self.create_window(padding,padding,window=self.body,anchor='nw')
        self.bind('<Configure>',lambda e:self.draw())
        self.body.bind('<Configure>',lambda e:self.fit())
    def fit(self):
        if not self.autosize:return
        needed=self.body.winfo_reqheight()+2*self.padding
        if int(self.cget('height'))!=needed:self.configure(height=needed)
    def draw(self):
        p=self.app.p;self.configure(bg=p['bg']);self.delete('shell')
        w,h=max(60,self.winfo_width()),max(8,self.winfo_height())
        if self.shadow:
            rounded(self,2,4,w-4,h-5,self.radius,fill=p.get('shadow',p['border']),outline='',tags='shell')
        rounded(self,1,1,w-2,h-(5 if self.shadow else 2),self.radius,fill=p[self.surface],
                outline=p[self.surface] if self.surface=='sidebar' else p['border'],width=1,tags='shell')
        if self.accent_top:
            r=min(self.radius,(w-2)/2,(h-2)/2)
            points=[]
            for cx,start in ((r+1,180),(w-r-1,270)):
                for step in range(13):
                    angle=math.radians(start+step*7.5)
                    points.extend((cx+r*math.cos(angle),r+1+r*math.sin(angle)))
            self.create_line(*points,fill=p['accent'],width=1.5,tags='shell')
        self.tag_lower('shell')
        self.itemconfigure(self.window,width=max(10,w-2*self.padding),height=max(10,h-2*self.padding))


class FormRow(RoundedPanel):
    """Une ligne du panneau de diagnostic, séparée par un simple filet."""
    def __init__(self,parent,app,last=False,**kwargs):
        self.last=last
        super().__init__(parent,app,**kwargs)

    def draw(self):
        p=self.app.p
        self.configure(bg=p['surface']);self.delete('shell')
        w,h=max(60,self.winfo_width()),max(8,self.winfo_height())
        if not self.last:self.create_line(4,h-1,w-4,h-1,fill=p['border'],tags='shell')
        self.tag_lower('shell')
        self.itemconfigure(self.window,width=max(10,w-2*self.padding),height=max(10,h-2*self.padding))


class RoundedField(tk.Canvas):
    def __init__(self,parent,app,value,changed):
        super().__init__(parent,height=54,width=180,highlightthickness=0,bg=app.p['bg'])
        self.app=app
        self.text=tk.Text(self,wrap='word',font=('Segoe UI',11),relief='flat',bd=0,
                          highlightthickness=0,padx=0,pady=0,undo=True,height=3)
        self.text.insert('1.0',value)
        self.window=self.create_window(12,8,window=self.text,anchor='nw')
        self.bind('<Configure>',lambda e:self.draw())
        self.text.bind('<FocusIn>',lambda e:self.draw())
        self.text.bind('<FocusOut>',lambda e:self.draw())
        self.text.edit_modified(False)
        def update(_e):
            if self.text.edit_modified():
                self.text.edit_modified(False)
                changed(self.text.get('1.0','end').strip())
        self.text.bind('<<Modified>>',update)

    def draw(self):
        p=self.app.p
        self.configure(bg=p['surface'])
        self.delete('shell')
        w=max(self.winfo_width(),40)
        h=max(24,self.winfo_height())
        pad_y=6 if h<36 else 8
        rounded(self,1,1,w-2,h-2,8,fill=p['input'],outline=p['accent'] if self.text.focus_get()==self.text else p['border'],width=1,tags='shell')
        self.tag_lower('shell')
        self.coords(self.window,12,pad_y)
        self.itemconfigure(self.window,width=max(w-24,10),height=max(18,h-2*pad_y))
        self.text.configure(bg=p['input'],fg=p['fg'],font=('Segoe UI',10 if h<36 else 11),insertbackground=p['fg'],selectbackground=p['accent'],selectforeground=p['accent_fg'])


class SearchBox(tk.Canvas):
    def __init__(self,parent,app,variable,radius=18):
        super().__init__(parent,height=52,width=180,highlightthickness=0)
        self.app=app
        self.radius=radius
        self.entry=tk.Entry(self,textvariable=variable,font=('Segoe UI',11),relief='flat',bd=0,highlightthickness=0)
        self.window=self.create_window(20,26,window=self.entry,anchor='w')
        self.bind('<Configure>',lambda e:self.draw())
        self.entry.bind('<FocusIn>',lambda e:self.draw())
        self.entry.bind('<FocusOut>',lambda e:self.draw())
    def draw(self):
        p=self.app.p;self.configure(bg=p['bg']);self.delete('shell')
        w=max(60,self.winfo_width())
        rounded(self,1,1,w-2,50,self.radius,fill=p['surface'],outline=p['accent'] if self.entry.focus_get()==self.entry else p['border'],width=1,tags='shell')
        self.tag_lower('shell');self.itemconfigure(self.window,width=max(20,w-40))
        self.entry.configure(bg=p['surface'],fg=p['fg'],insertbackground=p['fg'],selectbackground=p['accent'],selectforeground=p['accent_fg'])


class DiagnosticForm(ttk.Frame):
    def __init__(self,parent,app,resolve):
        super().__init__(parent)
        self.app,self.resolve=app,resolve
        self.fields={}
        self.path=visible_path(app.questions,app.answers,resolve,app.skipped)
        app.answers={i:v for i,v in app.answers.items() if i in self.path}
        app.skipped.intersection_update(self.path)
        app.history=list(self.path)
        self.counter=tk.StringVar()
        top=ttk.Frame(self);top.pack(fill='x',pady=(0,8));self.top=top
        root_answer=app.answer_text(0)
        self.heading=ttk.Label(top,text=f'Votre diagnostic · {root_answer}',style='Title.TLabel',wraplength=670)
        self.heading.pack(side='left')
        self.change_button=ttk.Button(top,text='Changer de poste',style='Ghost.TButton',command=self.change_root);self.change_button.pack(side='right')
        self.intro=ttk.Label(self,text=f'Poste {root_answer} · Complétez les réponses face aux questions. * Obligatoire.',style='Muted.TLabel',wraplength=850)
        self.intro.pack(anchor='w',pady=(0,6))
        footer=ttk.Frame(self);footer.pack(side='bottom',fill='x',pady=(8,0))
        ttk.Label(footer,textvariable=self.counter,style='Muted.TLabel').pack(side='left')
        ttk.Button(footer,text='Créer la synthèse  →',style='Accent.TButton',command=self.finish).pack(side='right')
        self.sheet=RoundedPanel(self,app,padding=8,radius=9,shadow=False,accent_top=True)
        self.sheet.pack(fill='both',expand=True)
        area=self.sheet.body
        self.canvas=tk.Canvas(area,bg=app.p['surface'],highlightthickness=0)
        self.canvas._surface_background=True
        sb=ttk.Scrollbar(area,command=self.canvas.yview);self.scrollbar=sb
        self.canvas.pack(side='left',fill='both',expand=True);self.canvas.configure(yscrollcommand=sb.set)
        self.rows=ttk.Frame(self.canvas,style='Surface.TFrame')
        self.window=self.canvas.create_window(0,0,window=self.rows,anchor='nw')
        self.canvas.bind('<Configure>',self.reflow)
        self.rows.bind('<Configure>',lambda e:self.update_scroll())
        self.rows.columnconfigure(0,weight=1)
        self.row_widgets=[]
        self.row_panels=[]
        for row,i in enumerate(self.path[1:]):
            q=app.questions[i]
            panel=FormRow(self.rows,app,padding=8,last=row==len(self.path)-2,autosize=False)
            panel.grid(row=row,column=0,sticky='ew')
            self.row_panels.append(panel)
            label=ttk.Label(panel.body,text=q['text']+(' *' if q['required'] else ''),style='Card.TLabel',wraplength=205,justify='left',font=('Segoe UI',11,'bold'))
            label.grid(row=0,column=0,sticky='w',padx=(4,16))
            if q['type']=='free':
                field=RoundedField(panel.body,app,app.answers.get(i,''),lambda value,index=i:self.record(index,value or None))
                field.grid(row=0,column=1,sticky='ew')
                self.fields[i]=field.text
            else:
                group=ttk.Frame(panel.body,style='Surface.TFrame');group.grid(row=0,column=1,sticky='ew')
                field=group
                variable=tk.StringVar(value=q['choices'][app.answers[i]] if i in app.answers else 'Choisir une réponse…')
                combo=ttk.Combobox(group,values=q['choices'],textvariable=variable,state='readonly',font=('Segoe UI',11))
                combo.pack(fill='x',ipady=6)
                combo.bind('<<ComboboxSelected>>',lambda e,index=i,w=combo:self.choose(index,w.current()))
                if not q['required']:
                    ttk.Button(group,text='Sans réponse',style='Card.Ghost.TButton',command=lambda index=i:self.choose(index,None)).pack(anchor='e',pady=(6,0))
                self.fields[i]=combo
            self.row_widgets.append((label,field))
        if self.path and app.questions[self.path[-1]]['type']=='choice' and self.path[-1] not in app.answers:
            ttk.Label(self.rows,text='Les questions suivantes s’adapteront à cette réponse.',style='Card.Muted.TLabel',wraplength=620).grid(row=len(self.path),column=0,columnspan=2,sticky='w',pady=16)
        if len(self.path)==1:
            ttk.Label(self.rows,text='Ce parcours est terminé. Vous pouvez créer la synthèse.',style='Card.H2.TLabel').grid(row=0,column=0,columnspan=2,pady=24)
        self.progress()
        def wheel(e):
            steps=-int(e.delta/120)
            if isinstance(e.widget,tk.Text) and e.widget.yview()!=(0.0,1.0):
                e.widget.yview_scroll(steps,'units')
            else:self.canvas.yview_scroll(steps,'units')
            return 'break'
        def bind_scroll(widget):
            widget.bind('<MouseWheel>',wheel)
            for child in widget.winfo_children():bind_scroll(child)
        bind_scroll(self.canvas)

    def reflow(self,event=None):
        width=max(self.canvas.winfo_width(),240)
        height=max(self.canvas.winfo_height(),200)
        self.canvas.itemconfigure(self.window,width=width)
        narrow=width<500
        label_width=min(260,max(150,int(width*.34)))
        count=max(1,len(self.row_widgets))
        compact=height<390
        padding=4 if compact else 8
        gap=0
        field_height=max(30 if compact else 34,min(54,(height-8)//count-(2*padding+gap+4)))
        for row,(label,field) in enumerate(self.row_widgets):
            panel=self.row_panels[row]
            panel.padding=padding
            panel.coords(panel.window,padding,padding)
            panel.grid_configure(pady=(0,gap))
            panel.body.columnconfigure(0,minsize=0 if narrow else label_width,weight=1 if narrow else 0)
            panel.body.columnconfigure(1,weight=0 if narrow else 1)
            label.configure(wraplength=width-50 if narrow else label_width-24,font=('Segoe UI',10 if compact else 11,'bold'))
            label.grid_configure(row=0,column=0,pady=(0,6) if narrow else 0)
            field.grid_configure(row=1 if narrow else 0,column=0 if narrow else 1,pady=0)
            if isinstance(field,RoundedField):field.configure(height=field_height)
            content_height=field_height if isinstance(field,RoundedField) else field.winfo_reqheight()
            content_height=(label.winfo_reqheight()+6+content_height) if narrow else max(label.winfo_reqheight(),content_height)
            panel.configure(height=content_height+2*padding)
            panel.draw()
        self.heading.configure(wraplength=max(180,self.winfo_width()-210),font=('Segoe UI',18 if width<700 or self.winfo_height()<520 else 22,'bold'))
        self.intro.configure(wraplength=max(200,width))

    def update_scroll(self):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        overflow=self.rows.winfo_reqheight()>self.canvas.winfo_height()+2
        if overflow and not self.scrollbar.winfo_manager():self.scrollbar.pack(side='right',fill='y',before=self.canvas)
        elif not overflow and self.scrollbar.winfo_manager():
            self.scrollbar.pack_forget();self.canvas.yview_moveto(0)

    def record(self,index,value):
        if value is None:self.app.answers.pop(index,None)
        else:self.app.answers[index]=value
        self.progress()

    def progress(self):
        count=sum(i in self.app.answers for i in self.path[1:])
        self.counter.set(f'{count} / {max(0,len(self.path)-1)} réponses renseignées')

    def collect(self):
        for i,field in self.fields.items():
            if isinstance(field,tk.Text):self.record(i,field.get('1.0','end').strip() or None)

    def choose(self,index,value):
        self.collect()
        self.record(index,value)
        if value is None:self.app.skipped.add(index)
        else:self.app.skipped.discard(index)
        self.app.show_form()

    def change_root(self):
        self.collect()
        self.app.current=0
        self.app.history=[0]
        self.app.show_question()

    def finish(self):
        self.collect()
        for i in self.path:
            if self.app.questions[i]['type']=='choice' and i not in self.app.answers and i not in self.app.skipped and not self.app.questions[i]['required']:
                self.app.warn('Choix attendu','Choisissez une réponse ou cliquez « Sans réponse » pour déterminer la suite du parcours.')
                return
        for i in self.path:
            if self.app.questions[i]['required'] and i not in self.app.answers:
                self.app.warn('Réponse manquante',f'Complétez « {self.app.questions[i]["text"]} » avant de créer la synthèse.')
                if i in self.fields:
                    field=self.fields[i]
                    self.update_idletasks()
                    y=field.winfo_rooty()-self.rows.winfo_rooty()
                    self.canvas.yview_moveto(max(0,y-25)/max(self.rows.winfo_height(),1))
                    field.focus_set()
                return
        self.app.history=list(self.path)
        self.app.show_result()
