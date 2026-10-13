"""Bibliothèque locale de procédures consultable et administrable."""
import json
import os
import tempfile
import unicodedata
import uuid
import tkinter as tk
from tkinter import ttk
from diagnostic_form import RoundedPanel, SearchBox, rounded

SYSTEMS=('Tous','Windows','Linux')


def load_articles(path):
    if not path.exists():return []
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('articles'),list):
        raise ValueError('Le fichier de documentation est invalide.')
    articles=data['articles']
    ids=set()
    for article in articles:
        if not isinstance(article,dict) or any(not isinstance(article.get(key),str) for key in ('id','title','system','category','keywords','content')):
            raise ValueError('Un article de documentation est invalide.')
        if not article['id'] or article['id'] in ids or article['system'] not in SYSTEMS:
            raise ValueError('Un article de documentation est invalide.')
        ids.add(article['id'])
    return articles


def save_articles(path,articles):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as file:
            temporary=file.name
            json.dump({'version':1,'articles':articles},file,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    finally:
        if temporary and os.path.exists(temporary):os.unlink(temporary)


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def search_articles(articles,query='',system='Tous'):
    terms=folded(query).split()
    result=[]
    for article in articles:
        if system!='Tous' and article['system'] not in ('Tous',system):continue
        haystack=folded(' '.join(article[k] for k in ('title','category','keywords','content','system')))
        if all(term in haystack for term in terms):result.append(article)
    return sorted(result,key=lambda a:folded(a['title']))


class ArticleList(tk.Canvas):
    """Liste compacte de procédures avec sélection et navigation au clavier."""
    def __init__(self,parent,app):
        super().__init__(parent,width=260,height=180,highlightthickness=0,
                         takefocus=True,yscrollincrement=24,bg=app.p['surface'])
        self.app=app
        self.articles=[]
        self.selected_id=None
        self.bounds=[]
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<FocusIn>',lambda e:self.draw())
        self.bind('<FocusOut>',lambda e:self.draw())
        self.bind('<Button-1>',self.click)
        self.bind('<MouseWheel>',self.wheel)
        for key in ('Up','Down','Home','End','Prior','Next'):
            self.bind('<'+key+'>',self.navigate)

    def set_articles(self,articles):
        self.articles=articles
        self.draw()

    def draw(self):
        p=self.app.p
        self.configure(bg=p['surface'])
        self.delete('all')
        self.bounds=[]
        width=max(180,self.winfo_width())
        y=1
        for index,article in enumerate(self.articles):
            selected=article['id']==self.selected_id
            title=self.create_text(13,y+12,text=article['title'],anchor='nw',
                width=width-28,font=('Segoe UI',10,'bold'),fill=p['fg'])
            title_bottom=self.bbox(title)[3]
            system='Tous les systèmes' if article['system']=='Tous' else article['system']
            metadata=' · '.join(filter(None,[article['category'],system]))
            meta=self.create_text(13,title_bottom+5,text=metadata,anchor='nw',
                width=width-28,font=('Segoe UI',9),fill=p['muted'])
            bottom=max(y+68,self.bbox(meta)[3]+12)
            if selected:
                card=rounded(self,1,y,width-3,bottom-y,5,
                    fill=p['select'],outline=p['accent'] if self.focus_get()==self else p['border'],width=1)
                self.tag_lower(card)
            if index<len(self.articles)-1:
                self.create_line(10,bottom,width-11,bottom,fill=p['border'],width=1)
            self.bounds.append((article['id'],y,bottom))
            y=bottom+1
        self.configure(scrollregion=(0,0,width,max(0,y)))

    def selection(self):
        return (self.selected_id,) if self.selected_id else ()

    def selection_set(self,article_id):
        if article_id not in {a['id'] for a in self.articles}:article_id=None
        changed=self.selected_id!=article_id
        self.selected_id=article_id
        self.draw()
        if changed:self.event_generate('<<ArticleSelect>>')

    def see(self,article_id):
        bounds=next((b for b in self.bounds if b[0]==article_id),None)
        if not bounds:return
        _,top,bottom=bounds
        viewport=max(1,self.winfo_height())
        current=self.canvasy(0)
        total=max(1,self.bounds[-1][2]+2)
        if top<current:self.yview_moveto(max(0,top-2)/total)
        elif bottom>current+viewport:self.yview_moveto(max(0,bottom-viewport+2)/total)

    def click(self,event):
        self.focus_set()
        y=self.canvasy(event.y)
        selected=next((i for i,top,bottom in self.bounds if top<=y<=bottom),None)
        if selected:self.selection_set(selected)

    def wheel(self,event):
        if self.yview()!=(0.0,1.0):self.yview_scroll(-int(event.delta/120),'units')
        return 'break'

    def navigate(self,event):
        if not self.articles:return 'break'
        ids=[a['id'] for a in self.articles]
        current=ids.index(self.selected_id) if self.selected_id in ids else 0
        page=max(1,self.winfo_height()//69)
        index={'Up':current-1,'Down':current+1,'Home':0,'End':len(ids)-1,
               'Prior':current-page,'Next':current+page}[event.keysym]
        selected=ids[max(0,min(index,len(ids)-1))]
        self.selection_set(selected);self.see(selected)
        return 'break'


class Documentation(ttk.Frame):
    def __init__(self,parent,app,path,editable=False):
        super().__init__(parent)
        self.app,self.path,self.editable=app,path,editable
        self.selected_id=None
        self.failed=False
        try:self.articles=load_articles(path)
        except (OSError,ValueError) as err:
            self.articles=[];self.failed=True
            app.error('Documentation indisponible',str(err))
        controls=ttk.Frame(self);controls.pack(fill='x',pady=(0,8))
        ttk.Label(controls,text='Rechercher',style='Muted.TLabel').pack(side='left',padx=(0,12))
        self.query=tk.StringVar()
        search_row=ttk.Frame(controls);search_row.pack(side='left',fill='x',expand=True)
        self.search_box=SearchBox(search_row,app,self.query,radius=8)
        self.search_box.pack(side='left',fill='x',expand=True)
        self.search=self.search_box.entry
        ttk.Button(search_row,text='Effacer',command=lambda:self.query.set('')).pack(side='right',padx=(8,0))
        self.system=tk.StringVar(value='Tous')
        filters=ttk.Frame(self);filters.pack(fill='x',pady=(0,8))
        self.filter_buttons={}
        for system in SYSTEMS:
            b=ttk.Button(filters,text='Tous les systèmes' if system=='Tous' else system,command=lambda s=system:self.system.set(s))
            b.pack(side='left',padx=(0,8));self.filter_buttons[system]=b
        self.count=tk.StringVar()
        ttk.Label(filters,textvariable=self.count,style='Muted.TLabel').pack(side='right')
        if editable:
            actions=ttk.Frame(self);actions.pack(side='bottom',fill='x',pady=(12,0))
            self.buttons=[]
            for label,command,style in [('+ Ajouter un article',lambda:self.edit_article(),'Accent.TButton'),('Modifier',self.edit_selected,'TButton'),('Supprimer',self.delete_selected,'Danger.TButton')]:
                b=ttk.Button(actions,text=label,command=command,style=style);b.pack(side='left',padx=(0,8));self.buttons.append(b)
                if self.failed:b.state(['disabled'])
        self.panes=ttk.Frame(self);self.panes.pack(fill='both',expand=True)
        self.panes.columnconfigure(1,weight=1);self.panes.rowconfigure(0,weight=1)
        self.list_frame=RoundedPanel(self.panes,app,padding=6,radius=8,shadow=False)
        self.list_frame.configure(width=280)
        self.list_frame.grid(row=0,column=0,sticky='nsew',padx=(0,14))
        self.listbox=ArticleList(self.list_frame.body,app)
        ls=ttk.Scrollbar(self.list_frame.body,command=self.listbox.yview)
        self.listbox.pack(side='left',fill='both',expand=True)
        def scroll_state(first,last):
            ls.set(first,last)
            if float(first)>0 or float(last)<1:
                if not ls.winfo_manager():ls.pack(side='right',fill='y',before=self.listbox)
            elif ls.winfo_manager():ls.pack_forget()
        self.listbox.configure(yscrollcommand=scroll_state)
        self.reader=RoundedPanel(self.panes,app,padding=20,radius=8,shadow=False)
        self.reader.grid(row=0,column=1,sticky='nsew')
        self.title=ttk.Label(self.reader.body,style='Card.H2.TLabel',wraplength=500)
        self.title.pack(anchor='w',fill='x')
        self.title.bind('<Configure>',lambda e:self.title.configure(wraplength=max(120,e.width)))
        self.metadata=ttk.Label(self.reader.body,style='Card.Ok.TLabel',wraplength=500)
        self.metadata.pack(anchor='w',pady=(4,12))
        self.metadata.bind('<Configure>',lambda e:self.metadata.configure(wraplength=max(120,e.width)))
        text_area=ttk.Frame(self.reader.body,style='Surface.TFrame');text_area.pack(fill='both',expand=True)
        self.content=app.make_text(text_area,height=1,width=1)
        sb=ttk.Scrollbar(text_area,command=self.content.yview)
        sb.pack(side='right',fill='y');self.content.pack(fill='both',expand=True)
        self.content.configure(yscrollcommand=sb.set,state='disabled')
        self.content._documentation_content=True
        app.paint(self.content)
        self.listbox.bind('<<ArticleSelect>>',self.select)
        self.query.trace_add('write',lambda *_:self.refresh())
        self.system.trace_add('write',lambda *_:self.refresh())
        self.panes.bind('<Configure>',self.reflow)
        self.refresh()

    def reflow(self,event):
        narrow=event.width<650
        list_width=max(220,min(300,int(event.width*.32)))
        self.list_frame.configure(width=list_width)
        self.listbox.configure(width=list_width-12,height=80 if narrow else 180)
        self.panes.columnconfigure(0,weight=1 if narrow else 0)
        self.panes.columnconfigure(1,weight=0 if narrow else 1)
        self.panes.rowconfigure(0,weight=0 if narrow else 1)
        self.panes.rowconfigure(1,weight=1 if narrow else 0)
        self.list_frame.grid_configure(row=0,column=0,padx=(0,0) if narrow else (0,14),pady=(0,10) if narrow else 0)
        self.reader.grid_configure(row=1 if narrow else 0,column=0 if narrow else 1)

    def refresh(self):
        self.results=search_articles(self.articles,self.query.get(),self.system.get())
        self.listbox.set_articles(self.results)
        for key,button in self.filter_buttons.items():button.configure(style='Accent.TButton' if key==self.system.get() else 'TButton')
        self.count.set('Fichier à vérifier' if self.failed else f'{len(self.results)} procédure(s)')
        index=next((i for i,a in enumerate(self.results) if a['id']==self.selected_id),0)
        if self.results:
            self.listbox.selection_set(self.results[index]['id']);self.listbox.see(self.results[index]['id'])
        else:self.listbox.selection_set(None)
        self.select()

    def select(self,_event=None):
        selected=self.listbox.selection()
        article=next((a for a in self.results if selected and a['id']==selected[0]),None)
        self.selected_id=article['id'] if article else None
        self.title.configure(text=article['title'] if article else 'Aucun article à afficher')
        self.metadata.configure(text=' · '.join(filter(None,[article['system'],article['category']])) if article else '')
        self.content.configure(state='normal');self.content.delete('1.0','end')
        self.content.insert('1.0',article['content'] if article else ('Aucun résultat pour cette recherche.\n\nEssayez un autre mot-clé ou choisissez « Tous les systèmes ».' if self.articles else 'Votre bibliothèque est prête.\n\nLa coordination peut ajouter les premières procédures depuis son espace.'))
        self.content.configure(state='disabled');self.content.yview_moveto(0)

    def can_edit(self):
        return self.editable and not self.failed and getattr(self.app,'session_user',None) in ('coordinateur','admin')

    def persist(self,articles):
        if not self.can_edit():return False
        try:save_articles(self.path,articles)
        except OSError as err:self.app.error('Enregistrement impossible',str(err));return False
        self.articles=articles
        self.refresh()
        return True

    def edit_selected(self):
        if self.selected_id:self.edit_article(next(a for a in self.articles if a['id']==self.selected_id))

    def edit_article(self,article=None):
        if not self.can_edit():return
        original=article or dict(id=uuid.uuid4().hex,title='',system='Tous',category='',keywords='',content='')
        win=tk.Toplevel(self.app);win.title('Modifier l’article' if article else 'Nouvel article');win.transient(self.app);win.grab_set()
        win.geometry('760x660');win.minsize(600,520)
        body=ttk.Frame(win,padding=22);body.pack(fill='both',expand=True)
        actions=ttk.Frame(body);actions.pack(side='bottom',fill='x',pady=(14,0))
        fields={}
        for label,key in [('Titre','title'),('Catégorie (ex. Réseau, Impression)','category'),('Mots-clés (ex. DNS, connexion, imprimante)','keywords')]:
            ttk.Label(body,text=label).pack(anchor='w')
            entry=ttk.Entry(body);entry.insert(0,original[key]);entry.pack(fill='x',pady=(4,10));fields[key]=entry
        ttk.Label(body,text='Système concerné').pack(anchor='w')
        system=tk.StringVar(value=original['system'])
        ttk.Combobox(body,textvariable=system,values=SYSTEMS,state='readonly').pack(fill='x',pady=(4,10))
        ttk.Label(body,text='Procédure / manipulations à effectuer').pack(anchor='w')
        area=ttk.Frame(body);area.pack(fill='both',expand=True,pady=(4,0))
        content=self.app.make_text(area,height=4,width=1)
        sb=ttk.Scrollbar(area,command=content.yview);sb.pack(side='right',fill='y')
        content.pack(fill='both',expand=True);content.configure(yscrollcommand=sb.set);content.insert('1.0',original['content'])
        def values():return dict(original,**{k:w.get().strip() for k,w in fields.items()},system=system.get(),content=content.get('1.0','end').rstrip('\n'))
        def close():
            if values()!=original and not self.app.confirm('Modifications non enregistrées','Fermer cet article sans enregistrer ?',yes='Fermer',no='Continuer'):
                win.grab_set();return
            win.destroy()
        def save():
            updated=values()
            if not updated['title'] or not updated['content'].strip():
                self.app.warn('Article incomplet','Saisissez un titre et le contenu de la procédure.');win.grab_set();return
            articles=[updated if a['id']==updated['id'] else a for a in self.articles]
            if article is None:articles.append(updated)
            if self.persist(articles):
                self.query.set('');self.system.set('Tous');self.selected_id=updated['id'];self.refresh();win.destroy()
            else:win.grab_set()
        ttk.Button(actions,text='Annuler',command=close).pack(side='left')
        ttk.Button(actions,text='Enregistrer l’article',style='Accent.TButton',command=save).pack(side='right')
        win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())
        fields['title'].focus_set()

    def delete_selected(self):
        if not self.can_edit() or not self.selected_id:return
        article=next(a for a in self.articles if a['id']==self.selected_id)
        if self.app.confirm('Supprimer l’article',f'Supprimer « {article["title"]} » de la documentation ?',yes='Supprimer',no='Annuler'):
            self.persist([a for a in self.articles if a['id']!=self.selected_id])
