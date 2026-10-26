import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch, Mock
from documentation import load_articles, save_articles, search_articles, source_target, Documentation
import droits
from test_routes import ndt


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class DocumentationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'documentation.json'
        self.articles=[dict(id='1',title='Connexion réseau',system='Windows',category='Réseau',keywords='DNS',content='Vérifier la résolution de noms.'),
                       dict(id='2',title='Imprimante',system='Tous',category='Matériel',keywords='papier',content='Contrôler le bac.'),
                       dict(id='3',title='Connexion Linux',system='Linux',category='Réseau',keywords='DNS',content='Vérifier la configuration.')]

    def test_roundtrip_and_search(self):
        self.assertEqual(load_articles(self.path),[])
        save_articles(self.path,self.articles)
        self.assertEqual(load_articles(self.path),self.articles)
        self.assertEqual([a['id'] for a in search_articles(self.articles,'resolution')],['1'])
        self.assertEqual(len(search_articles(self.articles)),3)
        self.assertEqual(search_articles(self.articles,'inexistant'),[])

    def test_software_sources_licenses_and_legacy_compatibility(self):
        software=dict(self.articles[0],sources=['https://example.com/setup',r'\\serveur\sources'],
                      licenses=[dict(service='Comptabilité',key='00123'),dict(service='Support',key='ABC-456')])
        save_articles(self.path,[software,self.articles[1]])
        self.assertEqual(load_articles(self.path),[software,self.articles[1]])
        self.assertEqual(search_articles([software],'comptabilite'),[software])
        self.assertEqual(search_articles([software],'example.com'),[software])
        for changes in ({'sources':'invalid'},{'sources':[123]},{'licenses':[{'service':'Support'}]}):
            save_articles(self.path,[dict(software,**changes)])
            with self.assertRaises(ValueError):load_articles(self.path)

    def test_network_source_opening(self):
        paths=[(r'\\serveur\partage\Mon logiciel',r'\\serveur\partage\Mon logiciel'),
               (r'"Z:\Logiciels BO"',r'Z:\Logiciels BO'),
               ('file://serveur/partage/Mon%20logiciel',r'\\serveur\partage\Mon logiciel')]
        reader=Mock()
        for source,expected in paths:
            self.assertEqual(source_target(source),('folder',expected))
            with patch('documentation.os.startfile') as launch:
                Documentation.open_source(reader,source)
                launch.assert_called_once_with(expected,'explore')
        with patch('documentation.webbrowser.open') as launch:
            Documentation.open_source(reader,'https://example.com/setup')
            launch.assert_called_once_with('https://example.com/setup')
        with patch('documentation.os.startfile',side_effect=OSError('Accès refusé')):
            Documentation.open_source(reader,paths[0][0])
            reader.app.error.assert_called_once()
        self.assertIsNone(source_target('simple commentaire'))

    def test_failed_save_preserves_articles(self):
        save_articles(self.path,self.articles)
        with patch('stockage.os.replace',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):save_articles(self.path,[])
        self.assertEqual(load_articles(self.path),self.articles)

    def test_reject_invalid_data(self):
        self.path.write_text('{}')
        with self.assertRaises(ValueError):load_articles(self.path)

    def test_coordinator_crud_and_public_reader(self):
        with patch.object(ndt,'DOCUMENTATION_FILE',self.path),patch.object(ndt,'SETTINGS_FILE',Path(self.temp.name)/'settings.json'):
            app=ndt.App(session=droits.session_bypass());app.withdraw()
            try:
                app.session_user='coordinateur';app.show_admin()
                editor=app.documentation_editor
                for index in (2,3,0,1,2):
                    app.notebook.buttons[index].invoke();app.update_idletasks()
                    self.assertEqual(app.notebook.select(),str(app.notebook.pages[index]))
                self.assertFalse(any(isinstance(w,ttk.Notebook) for w in descendants(app.notebook)))
                def submit(title,content,existing=None):
                    editor.edit_article(existing)
                    win=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel));win.withdraw()
                    entries=[w for w in descendants(win) if type(w)==ttk.Entry]
                    self.assertEqual(len(entries),1)
                    entries[0].delete(0,'end');entries[0].insert(0,title)
                    body=next(w for w in descendants(win) if isinstance(w,tk.Text))
                    body.delete('1.0','end');body.insert('1.0',content)
                    win.sources_text.delete('1.0','end');win.sources_text.insert('1.0','https://example.com/setup')
                    for item in win.license_list.get_children():win.license_list.delete(item)
                    win.license_list.insert('', 'end',values=('Service BO','00123-ABC'))
                    next(w for w in descendants(win) if isinstance(w,ttk.Button) and w.cget('text')=='Enregistrer le logiciel').invoke()
                    self.assertFalse(win.winfo_exists())
                submit('Test réseau','')
                saved=load_articles(self.path)[0]
                self.assertEqual(saved['sources'],['https://example.com/setup'])
                self.assertEqual(saved['licenses'],[{'service':'Service BO','key':'00123-ABC'}])
                submit('Test réseau modifié','Nouvelle étape',saved)
                self.assertEqual(load_articles(self.path)[0]['id'],saved['id'])
                app.show_documentation()
                self.assertFalse(app.documentation.can_edit())
                self.assertFalse(app.documentation.persist([]))
                app.documentation.query.set('nouvelle etape')
                self.assertEqual(len(app.documentation.results),1)
                self.assertEqual(app.documentation.content.cget('state'),'disabled')
                self.assertIn('Service BO : 00123-ABC',app.documentation.content.get('1.0','end'))
                self.assertIn('https://example.com/setup',app.documentation.content.get('1.0','end'))
                app.session_user='coordinateur';app.show_admin()
                with patch.object(app,'confirm',return_value=True):app.documentation_editor.delete_selected()
                self.assertEqual(load_articles(self.path),[])
            finally:app.destroy()

    def test_reader_and_home_fit_window_and_theme(self):
        save_articles(self.path,self.articles)
        with patch.object(ndt,'DOCUMENTATION_FILE',self.path),patch.object(ndt,'SETTINGS_FILE',Path(self.temp.name)/'settings.json'):
            app=ndt.App(session=droits.session_bypass());app.attributes('-alpha',0)
            try:
                for theme in ('light','dark'):
                    app.theme=theme;app.p=ndt.PALETTES[theme];app.apply_theme()
                    for size in ('800x600','1180x800'):
                        app.geometry(size)
                        app.show_home();app.update()
                        # L'accueil Pause Cafew défile : la recherche reste visible, le reste est atteignable.
                        accueil=app.pause_cafew
                        ouvrir=next(w for w in descendants(accueil) if isinstance(w,ttk.Button) and w.cget('text')=='Ouvrir')
                        self.assertLessEqual(ouvrir.winfo_rooty()+ouvrir.winfo_height(),app.winfo_rooty()+app.winfo_height())
                        if accueil.contenu.winfo_reqheight()>accueil.canvas.winfo_height()+2:
                            self.assertTrue(accueil.barre.winfo_manager())
                        app.show_documentation();app.update()
                        docs=app.documentation
                        self.assertGreater(docs.content.winfo_height(),100)
                        self.assertGreater(docs.content.winfo_width(),250)
                        self.assertGreater(docs.listbox.winfo_width(),180)
                        self.assertEqual(docs.content.cget('background'),app.p['surface'])
                        # L'écran est gardé en mémoire : il retrouve la recherche du passage précédent.
                        if theme!='light' or size!='800x600':
                            self.assertIs(docs,premier)
                            self.assertEqual(docs.query.get(),'configuration')
                        premier=docs
                        docs.query.set('')
                        self.assertEqual({a['id'] for a in docs.results},{'1','2','3'})
                        docs.query.set('configuration');app.update()
                        self.assertEqual(docs.selected_id,'3')
                        self.assertIn('configuration',docs.content.get('1.0','end'))
            finally:app.destroy()


if __name__=='__main__':unittest.main()
