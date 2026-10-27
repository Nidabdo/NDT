"""Catalogue de logiciels Wiki BO consultable et administrable."""
import json
import os
import ntpath
from urllib.parse import urlsplit, unquote
import unicodedata
import uuid
import webbrowser
import tkinter as tk
from fenetres import Popup, centrer_fenetre
from tkinter import ttk
from diagnostic_form import RoundedPanel, SearchBox, rounded, SectionNavigation
from article_images import ImageDocument, ArticleImageEditor, validate_images
from stockage import ecrire_json_atomique

SYSTEMS=('Tous','Windows','Linux')


def load_articles(path):
    if not path.exists():return []
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('articles'),list):
        raise ValueError('Le fichier du Wiki BO est invalide.')
    articles=data['articles']
    ids=set()
    for article in articles:
        if not isinstance(article,dict) or any(not isinstance(article.get(key),str) for key in ('id','title','content')):
            raise ValueError('Une fiche logiciel du Wiki BO est invalide.')
        if not article['id'] or article['id'] in ids:
            raise ValueError('Une fiche logiciel du Wiki BO est invalide.')
        ids.add(article['id'])
        if not isinstance(article.get('sources',[]),list) or any(not isinstance(v,str) for v in article.get('sources',[])):
            raise ValueError('Les sources du logiciel sont invalides.')
        licenses=article.get('licenses',[])
        if not isinstance(licenses,list) or any(not isinstance(v,dict) or any(not isinstance(v.get(k),str) for k in ('service','key')) for v in licenses):
            raise ValueError('Les licences du logiciel sont invalides.')
        validate_images(article)
    return articles


def save_articles(path,articles):
    ecrire_json_atomique(path,{'version':1,'articles':articles})


def load_wiki(path):
    """Initialise le fichier dédié et reprend l'ancienne bibliothèque une seule fois."""
    if path.exists():return load_articles(path)
    legacy=path.with_name('documentation.json')
    articles=load_articles(legacy) if path.name=='wiki_bo.json' and legacy.exists() else []
    save_articles(path,articles)
    return articles


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def search_articles(articles,query=''):
    terms=folded(query).split()
    result=[]
    for article in articles:
        haystack=folded(' '.join(article[k] for k in ('title','content')))
        haystack+=' '+folded(' '.join(article.get('sources',[]))+' '+' '.join(v['service'] for v in article.get('licenses',[])))
        if all(term in haystack for term in terms):result.append(article)
    return sorted(result,key=lambda a:folded(a['title']))


def source_target(source):
    """Reconnaît les URL web et les répertoires Windows sans accès réseau."""
    value=source.strip().strip('"')
    if value.lower().startswith(('https://','http://')):return 'web',value
    if value.lower().startswith('file://'):
        parsed=urlsplit(value)
        value=unquote(parsed.path)
        if parsed.netloc and parsed.netloc.lower()!='localhost':value='//'+parsed.netloc+value
        elif len(value)>2 and value[0]=='/' and value[2]==':':value=value[1:]
    value=value.replace('/',chr(92))
    drive,tail=ntpath.splitdrive(value)
    if (drive.startswith(chr(92)*2) and len(drive.strip(chr(92)).split(chr(92)))==2
            or len(drive)==2 and drive[1]==':' and tail.startswith(chr(92))):
        return 'folder',value
    return None


class ArticleList(tk.Canvas):
    """Liste compacte de procédures avec sélection et navigation au clavier."""
    def __init__(self,parent,app,show_metadata=True):
        self.show_metadata=show_metadata
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
            bottom=max(y+48,title_bottom+14)
            if self.show_metadata:
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
        try:self.articles=load_wiki(path)
        except (OSError,ValueError) as err:
            self.articles=[];self.failed=True
            app.error('Wiki BO indisponible',str(err))
        controls=ttk.Frame(self);controls.pack(fill='x',pady=(0,8))
        ttk.Label(controls,text='Rechercher',style='Muted.TLabel').pack(side='left',padx=(0,12))
        self.query=tk.StringVar()
        search_row=ttk.Frame(controls);search_row.pack(side='left',fill='x',expand=True)
        self.search_box=SearchBox(search_row,app,self.query,radius=8)
        self.search_box.pack(side='left',fill='x',expand=True)
        self.search=self.search_box.entry
        ttk.Button(search_row,text='Effacer',command=lambda:self.query.set('')).pack(side='right',padx=(8,0))
        self.count=tk.StringVar()
        ttk.Label(self,textvariable=self.count,style='Muted.TLabel').pack(anchor='e',pady=(0,8))
        if editable:
            actions=ttk.Frame(self);actions.pack(side='bottom',fill='x',pady=(12,0))
            self.buttons=[]
            for label,command,style in [('+ Ajouter un logiciel',lambda:self.edit_article(),'Accent.TButton'),('Modifier',self.edit_selected,'TButton'),('Supprimer',self.delete_selected,'Danger.TButton')]:
                b=ttk.Button(actions,text=label,command=command,style=style);b.pack(side='left',padx=(0,8));self.buttons.append(b)
                if self.failed:b.state(['disabled'])
        self.panes=ttk.Frame(self);self.panes.pack(fill='both',expand=True)
        self.panes.columnconfigure(1,weight=1);self.panes.rowconfigure(0,weight=1)
        self.list_frame=RoundedPanel(self.panes,app,padding=6,radius=8,shadow=False)
        self.list_frame.configure(width=280)
        self.list_frame.grid(row=0,column=0,sticky='nsew',padx=(0,14))
        self.listbox=ArticleList(self.list_frame.body,app,show_metadata=False)
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
        text_area=ttk.Frame(self.reader.body,style='Surface.TFrame');text_area.pack(fill='both',expand=True,pady=(12,0))
        self.content=app.make_text(text_area,height=1,width=1)
        sb=ttk.Scrollbar(text_area,command=self.content.yview)
        sb.pack(side='right',fill='y');self.content.pack(fill='both',expand=True)
        self.content.configure(yscrollcommand=sb.set,state='disabled')
        self.content._documentation_content=True
        self.image_document=ImageDocument(self.content)
        app.paint(self.content)
        self.listbox.bind('<<ArticleSelect>>',self.select)
        self.query.trace_add('write',lambda *_:self.refresh())
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
        self.results=search_articles(self.articles,self.query.get())
        self.listbox.set_articles(self.results)
        self.count.set('Fichier à vérifier' if self.failed else f'{len(self.results)} logiciel(s)')
        index=next((i for i,a in enumerate(self.results) if a['id']==self.selected_id),0)
        if self.results:
            self.listbox.selection_set(self.results[index]['id']);self.listbox.see(self.results[index]['id'])
        else:self.listbox.selection_set(None)
        self.select()

    def select(self,_event=None):
        selected=self.listbox.selection()
        article=next((a for a in self.results if selected and a['id']==selected[0]),None)
        self.selected_id=article['id'] if article else None
        self.title.configure(text=article['title'] if article else 'Aucun logiciel à afficher')
        self.content.configure(cursor='xterm')
        if article:
            sources=article.get('sources',[])
            licenses=article.get('licenses',[])
            prefix='SOURCES DU LOGICIEL\n'+('\n'.join(sources) or 'Non renseignées')
            prefix+='\n\nLICENCES PAR SERVICE\n'+('\n'.join(v['service']+' : '+v['key'] for v in licenses) or 'Non renseignées')
            prefix+='\n\nMÉTHODE D’INSTALLATION\n'
            self.image_document.load(prefix+article['content'],[dict(v,offset=v['offset']+len(prefix)) for v in article.get('images',[])])
            for tag in self.content.tag_names():
                if tag.startswith('source_'):self.content.tag_delete(tag)
            for i,source in enumerate(sources):
                if source_target(source):
                    tag=f'source_{i}';index=f'{i+2}.0'
                    self.content.tag_add(tag,index,f'{index}+{len(source)}c')
                    self.content.tag_configure(tag,underline=True)
                    self.content.tag_bind(tag,'<Button-1>',lambda e,url=source:self.open_source(url))
                    self.content.tag_bind(tag,'<Enter>',lambda e:self.content.configure(cursor='hand2'))
                    self.content.tag_bind(tag,'<Leave>',lambda e:self.content.configure(cursor='xterm'))
        else:
            self.image_document.load('Aucun résultat pour cette recherche.' if self.articles else 'Votre Wiki BO est prêt.\n\nAjoutez les logiciels depuis l’onglet Wiki BO de l’espace Coordination.')
        self.content.configure(state='disabled');self.content.yview_moveto(0)

    def open_source(self,source):
        target=source_target(source)
        if target:
            kind,value=target
            try:
                if kind=='web':webbrowser.open(value)
                else:os.startfile(value,'explore')
            except OSError as err:
                self.app.error('Source inaccessible',f'Impossible d’ouvrir cette source. Vérifiez le chemin et votre accès au réseau.\n\n{err}')
        return 'break'

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
        original=dict(article,images=article.get('images',[]),sources=article.get('sources',[]),licenses=article.get('licenses',[])) if article else dict(id=uuid.uuid4().hex,title='',content='',images=[],sources=[],licenses=[])
        win=Popup(self.app);win.title('Modifier le logiciel' if article else 'Nouveau logiciel');win.transient(self.app);win.grab_set()
        win.geometry('820x740');win.minsize(640,600)
        body=ttk.Frame(win,padding=22);body.pack(fill='both',expand=True)
        actions=ttk.Frame(body);actions.pack(side='bottom',fill='x',pady=(14,0))
        fields={}
        meta=ttk.Frame(body);meta.pack(fill='x');meta.columnconfigure(0,weight=1);meta.columnconfigure(1,weight=1)
        for label,key,row,col,span in [('Nom du logiciel','title',0,0,2)]:
            ttk.Label(meta,text=label).grid(row=row,column=col,columnspan=span,sticky='w')
            entry=ttk.Entry(meta);entry.insert(0,original[key]);entry.grid(row=row+1,column=col,columnspan=span,sticky='ew',pady=(4,8),padx=(0,8) if span==1 and col==0 else 0);fields[key]=entry
        notebook=SectionNavigation(body);notebook.pack(fill='both',expand=True,pady=(8,0))
        installation=ttk.Frame(notebook,padding=8)
        source_tab=ttk.Frame(notebook,padding=8)
        license_tab=ttk.Frame(notebook,padding=8)
        notebook.add(installation,text='Installation')
        notebook.add(source_tab,text='Sources')
        notebook.add(license_tab,text='Licences par service')
        ttk.Label(source_tab,text='Liens de téléchargement ou chemins réseau : une source par ligne.').pack(anchor='w',pady=(0,8))
        sources=self.app.make_text(source_tab,height=4,width=1)
        sources.pack(fill='both',expand=True)
        sources.insert('1.0','\n'.join(original['sources']))
        win.sources_text=sources
        ttk.Label(license_tab,text='Associez chaque clé à un service. Plusieurs clés par service sont possibles.',wraplength=550).pack(anchor='w',pady=(0,8))
        license_actions=ttk.Frame(license_tab);license_actions.pack(side='bottom',fill='x',pady=8)
        license_list=ttk.Treeview(license_tab,columns=('service','key'),show='headings',height=4,selectmode='browse')
        license_list.heading('service',text='Service');license_list.heading('key',text='Clé de licence')
        license_list.column('service',width=150);license_list.column('key',width=300)
        license_scroll=ttk.Scrollbar(license_tab,command=license_list.yview)
        license_scroll.pack(side='right',fill='y');license_list.pack(fill='both',expand=True)
        license_list.configure(yscrollcommand=license_scroll.set)
        for item in original['licenses']:license_list.insert('', 'end',values=(item['service'],item['key']))
        win.license_list=license_list
        def edit_license(existing=False):
            selected=license_list.selection()
            if existing and not selected:return
            item=selected[0] if existing else None
            dialog=Popup(win);dialog.title('Licence par service');dialog.transient(win);dialog.grab_set()
            form=ttk.Frame(dialog,padding=20);form.pack(fill='both',expand=True)
            entries=[]
            for label,value in zip(('Service','Clé de licence'),license_list.item(item,'values') if item else ('','')):
                ttk.Label(form,text=label).pack(anchor='w')
                entry=ttk.Entry(form,width=55);entry.insert(0,value);entry.pack(fill='x',pady=(4,10));entries.append(entry)
            def dismiss():dialog.destroy();win.grab_set()
            def accept():
                values=[entry.get().strip() for entry in entries]
                if not all(values):
                    self.app.warn('Licence incomplète','Renseignez le service et la clé de licence.');dialog.grab_set();return
                if item:license_list.item(item,values=values)
                else:license_list.insert('', 'end',values=values)
                dismiss()
            ttk.Button(form,text='Enregistrer la licence',command=accept).pack(side='right')
            ttk.Button(form,text='Annuler',command=dismiss).pack(side='left')
            dialog.protocol('WM_DELETE_WINDOW',dismiss);dialog.bind('<Escape>',lambda e:dismiss());entries[0].focus_set()
        ttk.Button(license_actions,text='Ajouter une licence',command=edit_license).pack(side='left')
        ttk.Button(license_actions,text='Modifier la licence',command=lambda:edit_license(True)).pack(side='left',padx=8)
        ttk.Button(license_actions,text='Retirer la licence',command=lambda:license_list.delete(*license_list.selection())).pack(side='left')
        toolbar=ttk.Frame(installation);toolbar.pack(fill='x',pady=(0,6))
        ttk.Label(installation,text='Ctrl+V pour coller · Cliquez sur une image puis tirez un coin pour la redimensionner.',wraplength=570).pack(anchor='w',pady=(0,8))
        ttk.Label(installation,text='Méthode d’installation').pack(anchor='w')
        area=ttk.Frame(installation);area.pack(fill='both',expand=True,pady=(4,0))
        content=self.app.make_text(area,height=4,width=1)
        sb=ttk.Scrollbar(area,command=content.yview);sb.pack(side='right',fill='y')
        content.pack(fill='both',expand=True);content.configure(yscrollcommand=sb.set)
        image_editor=ArticleImageEditor(content,toolbar,self.app,win)
        image_editor.load(original['content'],original['images']);win.image_editor=image_editor
        def values():
            text,images=image_editor.serialize()
            return dict(original,**{k:w.get().strip() for k,w in fields.items()},content=text,images=images,sources=[line.strip() for line in sources.get('1.0','end-1c').splitlines() if line.strip()],licenses=[dict(zip(('service','key'),license_list.item(item,'values'))) for item in license_list.get_children()])
        def close():
            if values()!=original and not self.app.confirm('Modifications non enregistrées','Fermer cette fiche sans enregistrer ?',yes='Fermer',no='Continuer'):
                win.grab_set();return
            win.destroy()
        def save():
            updated=values()
            if not updated['title']:
                self.app.warn('Logiciel incomplet','Saisissez le nom du logiciel.');win.grab_set();return
            articles=[updated if a['id']==updated['id'] else a for a in self.articles]
            if article is None:articles.append(updated)
            if self.persist(articles):
                self.query.set('');self.selected_id=updated['id'];self.refresh();win.destroy()
            else:win.grab_set()
        ttk.Button(actions,text='Annuler',command=close).pack(side='left')
        ttk.Button(actions,text='Enregistrer le logiciel',style='Accent.TButton',command=save).pack(side='right')
        win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())
        fields['title'].focus_set()

    def delete_selected(self):
        if not self.can_edit() or not self.selected_id:return
        article=next(a for a in self.articles if a['id']==self.selected_id)
        if self.app.confirm('Supprimer le logiciel',f'Supprimer « {article["title"]} » du Wiki BO ?',yes='Supprimer',no='Annuler'):
            self.persist([a for a in self.articles if a['id']!=self.selected_id])
