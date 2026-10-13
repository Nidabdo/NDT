import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch
from documentation import load_articles, save_articles, search_articles
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
        self.assertEqual([a['id'] for a in search_articles(self.articles,'RESEAU resolution')],['1'])
        self.assertEqual({a['id'] for a in search_articles(self.articles,'','Windows')},{'1','2'})
        self.assertEqual(search_articles(self.articles,'inexistant'),[])

    def test_failed_save_preserves_articles(self):
        save_articles(self.path,self.articles)
        with patch('documentation.os.replace',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):save_articles(self.path,[])
        self.assertEqual(load_articles(self.path),self.articles)

    def test_reject_invalid_data(self):
        self.path.write_text('{}')
        with self.assertRaises(ValueError):load_articles(self.path)

    def test_coordinator_crud_and_public_reader(self):
        with patch.object(ndt,'DOCUMENTATION_FILE',self.path),patch.object(ndt,'SETTINGS_FILE',Path(self.temp.name)/'settings.json'):
            app=ndt.App();app.withdraw()
            try:
                app.session_user='coordinateur';app.show_admin()
                editor=app.documentation_editor
                def submit(title,content,existing=None):
                    editor.edit_article(existing)
                    win=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel));win.withdraw()
                    entries=[w for w in descendants(win) if type(w)==ttk.Entry]
                    entries[0].delete(0,'end');entries[0].insert(0,title)
                    body=next(w for w in descendants(win) if isinstance(w,tk.Text))
                    body.delete('1.0','end');body.insert('1.0',content)
                    next(w for w in descendants(win) if isinstance(w,ttk.Button) and w.cget('text')=='Enregistrer l’article').invoke()
                    self.assertFalse(win.winfo_exists())
                submit('Test réseau','Première étape')
                saved=load_articles(self.path)[0]
                submit('Test réseau modifié','Nouvelle étape',saved)
                self.assertEqual(load_articles(self.path)[0]['id'],saved['id'])
                app.show_documentation()
                self.assertFalse(app.documentation.can_edit())
                self.assertFalse(app.documentation.persist([]))
                app.documentation.query.set('nouvelle etape')
                self.assertEqual(len(app.documentation.results),1)
                self.assertEqual(app.documentation.content.cget('state'),'disabled')
                app.session_user='coordinateur';app.show_admin()
                with patch.object(app,'confirm',return_value=True):app.documentation_editor.delete_selected()
                self.assertEqual(load_articles(self.path),[])
            finally:app.destroy()

    def test_reader_and_home_fit_window_and_theme(self):
        save_articles(self.path,self.articles)
        with patch.object(ndt,'DOCUMENTATION_FILE',self.path),patch.object(ndt,'SETTINGS_FILE',Path(self.temp.name)/'settings.json'):
            app=ndt.App();app.attributes('-alpha',0)
            try:
                for theme in ('light','dark'):
                    app.theme=theme;app.p=ndt.PALETTES[theme];app.apply_theme()
                    for size in ('800x600','1180x800'):
                        app.geometry(size)
                        app.show_home();app.update()
                        for button in (w for w in descendants(app.container) if isinstance(w,ttk.Button)):
                            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),app.winfo_rooty()+app.winfo_height())
                        app.show_documentation();app.update()
                        docs=app.documentation
                        self.assertGreater(docs.content.winfo_height(),100)
                        self.assertGreater(docs.content.winfo_width(),250)
                        self.assertGreater(docs.listbox.winfo_width(),180)
                        self.assertEqual(docs.content.cget('background'),app.p['surface'])
                        docs.system.set('Linux');app.update()
                        self.assertEqual({a['id'] for a in docs.results},{'2','3'})
                        docs.query.set('connexion');app.update()
                        self.assertEqual(docs.selected_id,'3')
                        self.assertIn('configuration',docs.content.get('1.0','end'))
            finally:app.destroy()


if __name__=='__main__':unittest.main()
