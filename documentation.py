"""Bibliothèque locale de procédures consultable et administrable."""
import json
import os
import tempfile
import unicodedata
import uuid
import tkinter as tk
from tkinter import ttk
from diagnostic_form import RoundedPanel, SearchBox

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
        self.search_box=SearchBox(search_row,app,self.query)
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
        self.list_frame=RoundedPanel(self.panes,app,padding=12)
        self.list_frame.grid(row=0,column=0,sticky='nsew',padx=(0,18))
        self.listbox=ttk.Treeview(self.list_frame.body,show='tree',selectmode='browse',style='Library.Treeview',height=3)
        self.listbox.column('#0',width=250,minwidth=160,stretch=True)
        ls=ttk.Scrollbar(self.list_frame.body,command=self.listbox.yview)
        ls.pack(side='right',fill='y');self.listbox.pack(side='left',fill='both',expand=True)
        self.listbox.configure(yscrollcommand=ls.set)
        self.reader=RoundedPanel(self.panes,app,padding=20)
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
        self.listbox.bind('<<TreeviewSelect>>',self.select)
        self.query.trace_add('write',lambda *_:self.refresh())
        self.system.trace_add('write',lambda *_:self.refresh())
        self.panes.bind('<Configure>',self.reflow)
        self.refresh()

    def reflow(self,event):
        narrow=event.width<650
        self.list_frame.configure(width=max(220,min(300,int(event.width*.32))))
        self.panes.columnconfigure(0,weight=1 if narrow else 0)
        self.panes.columnconfigure(1,weight=0 if narrow else 1)
        self.panes.rowconfigure(0,weight=0 if narrow else 1)
        self.panes.rowconfigure(1,weight=1 if narrow else 0)
        self.list_frame.grid_configure(row=0,column=0,padx=(0,0) if narrow else (0,18),pady=(0,10) if narrow else 0)
        self.listbox.configure(height=2 if narrow else 3)
        self.listbox.column('#0',width=max(160,min(270,int(event.width*.32)))-24)
        self.reader.grid_configure(row=1 if narrow else 0,column=0 if narrow else 1)

    def refresh(self):
        self.results=search_articles(self.articles,self.query.get(),self.system.get())
        self.listbox.delete(*self.listbox.get_children())
        for a in self.results:
            title=a['title'] if len(a['title'])<=30 else a['title'][:27]+'…'
            metadata=' · '.join(filter(None,[a['system'],a['category']]))
            self.listbox.insert('','end',iid=a['id'],text=title+'\n'+metadata[:38])
        for key,button in self.filter_buttons.items():button.configure(style='Accent.TButton' if key==self.system.get() else 'TButton')
        self.count.set('Fichier à vérifier' if self.failed else f'{len(self.results)} procédure(s)')
        index=next((i for i,a in enumerate(self.results) if a['id']==self.selected_id),0)
        if self.results:
            self.listbox.selection_set(self.results[index]['id']);self.listbox.see(self.results[index]['id'])
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
