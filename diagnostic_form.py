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


def style_rounded_button(app,name,bg,hover):
    if not hasattr(app,'button_images'):app.button_images={}
    element=name.replace('.','')+'.rounded'
    images=app.button_images.get(name)
    if images is None:
        images=[tk.PhotoImage(master=app,width=48,height=48) for _ in range(3)]
        app.button_images[name]=images
        app.style.element_create(element,'image',images[0],('pressed',images[1]),('active',images[1]),('focus',images[2]),border=20,padding=0,sticky='nsew')
        app.style.layout(name,[(element,{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
    for index,(image,color) in enumerate(zip(images,[bg,hover,bg])):
        image.blank()
        for y in range(48):
            distance=max(0,18-min(y,47-y)-0.5)
            left=max(0,math.ceil(18-math.sqrt(max(0,324-distance*distance))))
            image.put(app.p['fg'] if index==2 else color,to=(left,y,48-left,y+1))
            if index==2 and 2<=y<46:
                image.put(color,to=(min(left+2,23),y,max(48-left-2,25),y+1))


def rounded(canvas,x,y,w,h,r,**kw):
    r=min(r,w/2,h/2)
    points=[]
    for cx,cy,start in [(x+w-r,y+r,-90),(x+w-r,y+h-r,0),(x+r,y+h-r,90),(x+r,y+r,180)]:
        for step in range(13):
            a=math.radians(start+step*7.5)
            points.extend((cx+r*math.cos(a),cy+r*math.sin(a)))
    return canvas.create_polygon(*points,**kw)


class RoundedPanel(tk.Canvas):
    def __init__(self,parent,app,padding=24):
        super().__init__(parent,bg=app.p['bg'],highlightthickness=0,width=100,height=160)
        self.app,self.padding=app,padding
        self.body=ttk.Frame(self,style='Surface.TFrame')
        self.window=self.create_window(padding,padding,window=self.body,anchor='nw')
        self.bind('<Configure>',lambda e:self.draw())
        self.body.bind('<Configure>',lambda e:self.fit())
    def fit(self):
        needed=self.body.winfo_reqheight()+2*self.padding
        if int(self.cget('height'))!=needed:self.configure(height=needed)
    def draw(self):
        p=self.app.p;self.configure(bg=p['bg']);self.delete('shell')
        w,h=max(60,self.winfo_width()),max(60,self.winfo_height())
        rounded(self,1,1,w-2,h-2,30,fill=p['surface'],outline=p['border'],width=1,tags='shell')
        self.tag_lower('shell')
        self.itemconfigure(self.window,width=max(10,w-2*self.padding),height=max(10,h-2*self.padding))


class RoundedField(tk.Canvas):
    def __init__(self,parent,app,value,changed):
        super().__init__(parent,height=54,width=180,highlightthickness=0,bg=app.p['bg'])
        self.app=app
        self.text=tk.Text(self,wrap='word',font=('Segoe UI',11),relief='flat',bd=0,
                          highlightthickness=0,padx=0,pady=0,undo=True,height=3)
        self.text.insert('1.0',value)
        self.window=self.create_window(15,12,window=self.text,anchor='nw')
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
        self.configure(bg=p['bg'])
        self.delete('shell')
        w=max(self.winfo_width(),40)
        h=max(40,self.winfo_height())
        rounded(self,2,2,w-4,h-4,24,fill=p['surface'],outline=p['accent'] if self.text.focus_get()==self.text else p['border'],width=2,tags='shell')
        self.tag_lower('shell')
        self.itemconfigure(self.window,width=max(w-32,10),height=max(20,h-24))
        self.text.configure(bg=p['surface'],fg=p['fg'],insertbackground=p['fg'],selectbackground=p['accent'],selectforeground=p['accent_fg'])


class SearchBox(tk.Canvas):
    def __init__(self,parent,app,variable):
        super().__init__(parent,height=52,width=180,highlightthickness=0)
        self.app=app
        self.entry=tk.Entry(self,textvariable=variable,font=('Segoe UI',11),relief='flat',bd=0,highlightthickness=0)
        self.window=self.create_window(20,26,window=self.entry,anchor='w')
        self.bind('<Configure>',lambda e:self.draw())
        self.entry.bind('<FocusIn>',lambda e:self.draw())
        self.entry.bind('<FocusOut>',lambda e:self.draw())
    def draw(self):
        p=self.app.p;self.configure(bg=p['bg']);self.delete('shell')
        w=max(60,self.winfo_width())
        rounded(self,1,1,w-2,50,18,fill=p['surface'],outline=p['accent'] if self.entry.focus_get()==self.entry else p['border'],width=1,tags='shell')
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
        self.change_button=ttk.Button(top,text='Changer de poste',command=self.change_root);self.change_button.pack(side='right')
        self.intro=ttk.Label(self,text='Complétez votre parcours. * Réponse obligatoire.',style='Muted.TLabel',wraplength=850)
        self.intro.pack(anchor='w',pady=(0,8))
        footer=ttk.Frame(self);footer.pack(side='bottom',fill='x',pady=(18,0))
        ttk.Label(footer,textvariable=self.counter,style='Muted.TLabel').pack(side='left')
        ttk.Button(footer,text='Créer la synthèse  →',style='Accent.TButton',command=self.finish).pack(side='right')
        area=ttk.Frame(self);area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(area,bg=app.p['bg'],highlightthickness=0)
        sb=ttk.Scrollbar(area,command=self.canvas.yview);self.scrollbar=sb
        self.canvas.pack(side='left',fill='both',expand=True);self.canvas.configure(yscrollcommand=sb.set)
        self.rows=ttk.Frame(self.canvas)
        self.window=self.canvas.create_window(0,0,window=self.rows,anchor='nw')
        self.canvas.bind('<Configure>',self.reflow)
        self.rows.bind('<Configure>',lambda e:self.update_scroll())
        self.rows.columnconfigure(0,weight=0,minsize=230)
        self.rows.columnconfigure(1,weight=1)
        self.row_widgets=[]
        for row,i in enumerate(self.path[1:]):
            q=app.questions[i]
            label=ttk.Label(self.rows,text=q['text']+(' *' if q['required'] else ''),wraplength=205,justify='left',font=('Segoe UI',11,'bold'))
            label.grid(row=row,column=0,sticky='w',padx=(0,18),pady=6)
            if q['type']=='free':
                field=RoundedField(self.rows,app,app.answers.get(i,''),lambda value,index=i:self.record(index,value or None))
                field.grid(row=row,column=1,sticky='ew',padx=(0,4),pady=5)
                self.fields[i]=field.text
            else:
                group=ttk.Frame(self.rows);group.grid(row=row,column=1,sticky='ew',padx=(0,4),pady=5)
                field=group
                variable=tk.StringVar(value=q['choices'][app.answers[i]] if i in app.answers else 'Choisir une réponse…')
                combo=ttk.Combobox(group,values=q['choices'],textvariable=variable,state='readonly',font=('Segoe UI',11))
                combo.pack(fill='x',ipady=6)
                combo.bind('<<ComboboxSelected>>',lambda e,index=i,w=combo:self.choose(index,w.current()))
                if not q['required']:
                    ttk.Button(group,text='Sans réponse',command=lambda index=i:self.choose(index,None)).pack(anchor='e',pady=(6,0))
                self.fields[i]=combo
            self.row_widgets.append((label,field))
        if self.path and app.questions[self.path[-1]]['type']=='choice' and self.path[-1] not in app.answers:
            ttk.Label(self.rows,text='Les questions suivantes s’adapteront à cette réponse.',style='Muted.TLabel',wraplength=620).grid(row=len(self.path),column=0,columnspan=2,sticky='w',pady=16)
        if len(self.path)==1:
            ttk.Label(self.rows,text='Ce parcours est terminé. Vous pouvez créer la synthèse.',style='H2.TLabel').grid(row=0,column=0,columnspan=2,pady=24)
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
        label_width=min(260,max(150,int(width*.30)))
        self.rows.columnconfigure(0,minsize=0 if narrow else label_width,weight=1 if narrow else 0)
        self.rows.columnconfigure(1,weight=0 if narrow else 1)
        count=max(1,len(self.row_widgets))
        field_height=max(46,min(72,(height-12)//count-12))
        for row,(label,field) in enumerate(self.row_widgets):
            label.configure(wraplength=width-20 if narrow else label_width-20)
            label.grid_configure(row=row*2 if narrow else row,column=0,pady=(8,2) if narrow else 5)
            field.grid_configure(row=row*2+1 if narrow else row,column=0 if narrow else 1,pady=(0,6) if narrow else 5)
            if isinstance(field,RoundedField):field.configure(height=field_height)
        self.heading.configure(wraplength=max(180,self.winfo_width()-210),font=('Segoe UI',18 if width<700 else 24,'bold'))
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
