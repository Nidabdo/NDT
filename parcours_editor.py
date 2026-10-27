"""Éditeur visuel des parcours NDT, sans dépendance externe."""
import copy
import tkinter as tk
from fenetres import Popup, centrer_fenetre
import uuid
from tkinter import ttk
from diagnostic_form import rounded


def validate_links(questions):
    ids = {q['id'] for q in questions}
    graph = {}
    for i, q in enumerate(questions):
        routes = list(q.get('routes', [])) if q['type'] == 'choice' else [q.get('next', '')]
        if q['type'] == 'choice' and not q.get('required', True):
            routes.append(q.get('next', ''))
        following = questions[i + 1]['id'] if i + 1 < len(questions) else '__END__'
        targets = [r or following for r in routes]
        if any(t not in ids and t != '__END__' for t in targets):
            raise ValueError('Une destination est introuvable.')
        graph[q['id']] = [t for t in targets if t != '__END__']
    visiting, done = set(), set()
    def visit(node):
        if node in visiting:
            raise ValueError('Ce lien crée une boucle : le diagnostic reviendrait à une question déjà posée.')
        if node in done:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.remove(node)
        done.add(node)
    for node in graph:
        visit(node)


def reordered(questions, source, target):
    result = copy.deepcopy(questions)
    result.insert(target, result.pop(source))
    validate_links(result)
    return result


class ParcoursEditor(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_id = None
        self.drag = None
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', pady=(0, 12))
        ttk.Button(toolbar, text='+ Ajouter une question', style='Accent.TButton', command=self.add).pack(side='left')
        ttk.Button(toolbar, text='Modifier le bloc', command=self.edit).pack(side='left', padx=8)
        ttk.Button(toolbar, text='Supprimer', command=self.delete).pack(side='left')
        self.status = tk.StringVar(value='Vos modifications sont enregistrées automatiquement.')
        ttk.Label(self, text='Glissez l’en-tête d’un bloc pour changer l’ordre. Cliquez une réponse pour choisir sa destination.',
                  style='Muted.TLabel', wraplength=850).pack(anchor='w', pady=(0, 10))
        layout = ttk.Frame(self)
        layout.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(layout, highlightthickness=0, bg=app.p['bg'], takefocus=True)
        scroll = ttk.Scrollbar(layout, command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.motion)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Double-Button-1>', lambda e: self.edit())
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta / 120), 'units'))
        self.canvas.bind('<Alt-Up>', lambda e: self.move_selected(-1))
        self.canvas.bind('<Alt-Down>', lambda e: self.move_selected(1))
        ttk.Label(self, textvariable=self.status, style='Muted.TLabel', wraplength=850).pack(anchor='w', pady=(10, 0))
        self.draw()

    def index(self):
        return next((i for i, q in enumerate(self.app.questions) if q['id'] == self.selected_id), None)

    def commit(self, questions):
        try:
            validate_links(questions)
        except ValueError as err:
            self.app.warn('Parcours à corriger', str(err))
            return False
        old = self.app.questions
        self.app.questions = questions
        if not self.app.persist():
            self.app.questions = old
            return False
        self.status.set('Enregistré. Les liens explicites restent attachés à leurs questions.')
        self.draw()
        self.app.refresh_placeholders()
        return True

    def destination(self, value, index):
        if value == '__END__' or (not value and index == len(self.app.questions)-1):
            return 'Fin du diagnostic'
        if not value:
            return f'Bloc suivant · {index+2}'
        for i, q in enumerate(self.app.questions):
            if q['id'] == value:
                return f'{i+1}. {q["text"]}'
        return 'Destination supprimée — à corriger'

    def draw(self):
        c, p = self.canvas, self.app.p
        c.configure(bg=p['bg'])
        c.delete('all')
        self.boxes = []
        self.hits = []
        width = max(c.winfo_width(), 500)
        right = max(360, width-150)
        y = 20
        if not self.app.questions:
            c.create_text(28, 40, anchor='nw', text='Votre parcours commence ici.\nAjoutez votre première question.',
                          fill=p['muted'], font=('Segoe UI', 15))
        for i, q in enumerate(self.app.questions):
            rows = list(zip(q['choices'], q.get('routes', []))) if q['type']=='choice' else [('Après la réponse', q.get('next',''))]
            if q['type']=='choice' and not q.get('required',True):
                rows.append(('Sans réponse',q.get('next','')))
            h = 68 + 38*len(rows)
            self.boxes.append((y, y+h))
            rounded(c,22,y,right-22,h,20,fill=p['surface'],outline=p['accent'] if q['id']==self.selected_id else p['border'],width=2)
            prefix = 'DÉPART' if i==0 else f'QUESTION {i+1}'
            c.create_text(38,y+13,anchor='nw',text=f'☰  {prefix}     ·     Glisser pour déplacer',fill=p['accent'],font=('Segoe UI',9,'bold'))
            title=q['text'] if len(q['text'])<65 else q['text'][:62]+'…'
            c.create_text(38,y+36,anchor='nw',text=title,width=right-70,fill=p['fg'],font=('Segoe UI',12,'bold'))
            for row, (answer, route) in enumerate(rows):
                yy=y+68+row*38
                c.create_line(38,yy-4,right-16,yy-4,fill=p['border'])
                left_text=answer if len(answer)<29 else answer[:26]+'…'
                target=self.destination(route,i)
                if len(target)>36: target=target[:33]+'…'
                c.create_text(40,yy+10,anchor='w',text=left_text,fill=p['fg'],font=('Segoe UI',10))
                c.create_text(right-18,yy+10,anchor='e',text='→ '+target+'  ▾',fill=p['accent'],font=('Segoe UI',10))
                self.hits.append((i,row,yy-4,yy+32))
            y+=h+40
        # Les flèches montrent les destinations, y compris les sauts entre branches.
        for i, row, yy, _ in self.hits:
            q=self.app.questions[i]
            route=(q.get('routes',[])[row] if q['type']=='choice' and row<len(q['choices']) else q.get('next',''))
            target=(i+1 if i+1<len(self.boxes) else None) if not route else next((j for j,v in enumerate(self.app.questions) if v['id']==route),None)
            if target is not None:
                lane=right+20+(i%5)*16
                end=self.boxes[target][0]+24
                c.create_line(right,yy+14,lane,yy+14,lane,end,right,end,fill=p['accent'] if q['id']==self.selected_id else p['border'],arrow='last',width=2)
        c.configure(scrollregion=(0,0,width,y+20))

    def press(self,e):
        self.canvas.focus_set()
        y=self.canvas.canvasy(e.y)
        i=next((i for i,(a,b) in enumerate(self.boxes) if a<=y<=b),None)
        if i is None:return
        self.selected_id=self.app.questions[i]['id']
        self.drag=(i,e.y,y<self.boxes[i][0]+65)
        self.draw()

    def motion(self,e):
        if not self.drag or not self.drag[2]:return
        if e.y<35:self.canvas.yview_scroll(-1,'units')
        elif e.y>self.canvas.winfo_height()-35:self.canvas.yview_scroll(1,'units')
        self.canvas.delete('drop')
        y=self.canvas.canvasy(e.y)
        target=min(range(len(self.boxes)),key=lambda i:abs(y-sum(self.boxes[i])/2))
        yy=self.boxes[target][0] if target<=self.drag[0] else self.boxes[target][1]+15
        self.canvas.create_line(22,yy,self.canvas.winfo_width()-140,yy,fill=self.app.p['accent'],width=4,tags='drop')

    def release(self,e):
        if not self.drag:return
        source,start,header=self.drag
        self.drag=None
        y=self.canvas.canvasy(e.y)
        self.canvas.delete('drop')
        if header and abs(e.y-start)>8:
            target=min(range(len(self.boxes)),key=lambda i:abs(y-sum(self.boxes[i])/2))
            self.reorder(source,target)
        elif not header:
            row=next((row for i,row,a,b in self.hits if i==source and a<=y<=b),None)
            if row is not None:self.choose_target(source,row)

    def reorder(self,source,target):
        if source==target:return
        try: result=reordered(self.app.questions,source,target)
        except ValueError as err:
            self.app.warn('Déplacement impossible',str(err));return
        self.commit(result)

    def move_selected(self,delta):
        i=self.index()
        if i is not None and 0<=i+delta<len(self.app.questions):self.reorder(i,i+delta)

    def options(self,current):
        return [('Bloc suivant dans l’ordre','')]+[(f'{i+1}. {q["text"]}',q['id']) for i,q in enumerate(self.app.questions) if q['id']!=current]+[('Fin du diagnostic','__END__')]

    def choose_target(self,index,row):
        q=self.app.questions[index]
        win=Popup(self.app);win.title('Choisir la suite');win.transient(self.app);win.grab_set()
        body=ttk.Frame(win,padding=24);body.pack(fill='both',expand=True)
        answer=q['choices'][row] if q['type']=='choice' and row<len(q['choices']) else 'Après la réponse'
        ttk.Label(body,text=f'« {answer} » mène vers…',style='H2.TLabel',wraplength=500).pack(anchor='w',pady=(0,16))
        options=self.options(q['id'])
        route=q['routes'][row] if q['type']=='choice' and row<len(q['choices']) else q.get('next','')
        combo=ttk.Combobox(body,values=[label for label,_ in options],state='readonly',width=55)
        combo.pack(fill='x');combo.current(next((i for i,(_,v) in enumerate(options) if v==route),0))
        def save():
            questions=copy.deepcopy(self.app.questions)
            value=options[combo.current()][1]
            if q['type']=='choice' and row<len(q['choices']):questions[index]['routes'][row]=value
            else:questions[index]['next']=value
            if self.commit(questions):win.destroy()
        ttk.Button(body,text='Relier les questions',style='Accent.TButton',command=save).pack(anchor='e',pady=(18,0))
        win.bind('<Escape>',lambda e:win.destroy())

    def add(self):self.form(None)
    def edit(self):
        i=self.index()
        if i is None:self.app.info('Choisir un bloc','Cliquez d’abord sur le bloc à modifier.');return
        self.form(i)

    def form(self,index):
        old=copy.deepcopy(self.app.questions[index]) if index is not None else {'id':uuid.uuid4().hex[:8],'text':'','type':'choice','choices':[],'routes':[],'required':True,'next':''}
        win=Popup(self.app);win.title('Modifier la question' if index is not None else 'Nouvelle question');win.transient(self.app);win.grab_set()
        win.geometry('620x560');win.minsize(540,500)
        body=ttk.Frame(win,padding=24);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Que souhaitez-vous demander ?',style='H2.TLabel').pack(anchor='w')
        title=ttk.Entry(body);title.pack(fill='x',pady=(10,18));title.insert(0,old['text']);title.focus_set()
        kind=tk.StringVar(value=old['type'])
        row=ttk.Frame(body);row.pack(fill='x')
        choices=self.app.make_text(body,height=5)
        def update():choices.configure(state='normal' if kind.get()=='choice' else 'disabled')
        for label,value in [('Choix de réponses','choice'),('Texte libre','free')]:
            ttk.Radiobutton(row,text=label,value=value,variable=kind,command=update).pack(side='left',padx=(0,20))
        required=tk.BooleanVar(value=old['required'])
        ttk.Checkbutton(body,text='Réponse obligatoire',variable=required).pack(anchor='w',pady=12)
        ttk.Label(body,text='Réponses possibles · une par ligne',style='Muted.TLabel').pack(anchor='w')
        choices.pack(fill='both',expand=True,pady=(6,12));choices.insert('1.0','\n'.join(old['choices']));update()
        ttk.Label(body,text='Après l’enregistrement, cliquez une réponse sur le bloc pour choisir sa suite.',style='Muted.TLabel',wraplength=550).pack(anchor='w')
        def save():
            text=title.get().strip()
            values=[s.strip() for s in choices.get('1.0','end').splitlines() if s.strip()] if kind.get()=='choice' else []
            if not text or (kind.get()=='choice' and (len(values)<2 or len(set(values))!=len(values))):
                self.app.warn('Question incomplète','Saisissez un intitulé et au moins deux réponses différentes, ou choisissez Texte libre.');return
            mapping=dict(zip(old['choices'],old['routes']))
            q=dict(old,text=text,type=kind.get(),choices=values,routes=[mapping.get(v,'') for v in values],required=required.get())
            if 'tag' not in q:
                tags={item['tag'] for item in self.app.questions};n=1
                while f'q{n}' in tags:n+=1
                q['tag']=f'q{n}'
            questions=copy.deepcopy(self.app.questions)
            if index is None:questions.append(q)
            else:questions[index]=q
            if self.commit(questions):
                self.selected_id=q['id'];self.draw();win.destroy()
        actions=ttk.Frame(body);actions.pack(fill='x',pady=(18,0))
        ttk.Button(actions,text='Annuler',command=win.destroy).pack(side='left')
        ttk.Button(actions,text='Enregistrer le bloc',style='Accent.TButton',command=save).pack(side='right')
        win.bind('<Escape>',lambda e:win.destroy())

    def delete(self):
        i=self.index()
        if i is None:return
        q=self.app.questions[i]
        incoming=[v['text'] for v in self.app.questions if v['id']!=q['id'] and (q['id'] in v.get('routes',[]) or v.get('next')==q['id'])]
        if incoming:self.app.warn('Bloc encore relié','Changez d’abord les liens provenant de :\n'+'\n'.join(incoming));return
        if self.app.confirm('Supprimer le bloc',f'Supprimer « {q["text"]} » ?',yes='Supprimer',no='Annuler'):
            questions=copy.deepcopy(self.app.questions);questions.pop(i)
            if self.commit(questions):self.selected_id=None
