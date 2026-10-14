import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tkinter import ttk
from PIL import Image
from article_images import ImageDocument, ArticleImageEditor, encode_image, validate_images
from documentation import save_articles, load_articles
from test_documentation import descendants
import droits
from test_routes import ndt


class ArticleImagesTest(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.attributes('-alpha',0);self.root.geometry('700x500')
        self.addCleanup(self.root.destroy)
        self.toolbar=ttk.Frame(self.root);self.toolbar.pack(fill='x')
        self.text=tk.Text(self.root);self.text.pack(fill='both',expand=True)
        self.root.update()
        self.app=SimpleNamespace(error=Mock())
        self.editor=ArticleImageEditor(self.text,self.toolbar,self.app,self.root)
        self.source=Image.new('RGB',(400,200),'teal')

    def test_clipboard_image_and_text_paste_event(self):
        self.text.insert('1.0','Avant\nAprès');self.text.mark_set('insert','2.0')
        with patch('article_images.ImageGrab.grabclipboard',return_value=self.source):
            self.text.event_generate('<<Paste>>');self.root.update()
        text,images=self.editor.serialize()
        self.assertEqual(text,'Avant\nAprès');self.assertEqual(images[0]['offset'],6)
        self.assertEqual(len(images),1)
        with patch('article_images.ImageGrab.grabclipboard',return_value=None),patch.object(self.text,'clipboard_get',return_value='Texte collé'):
            self.text.tag_add('sel','1.0','1.5');self.text.mark_set('insert','1.0')
            self.text.event_generate('<<Paste>>')
        self.assertTrue(self.editor.serialize()[0].startswith('Texte collé\n'))
        self.app.error.assert_not_called()

    def test_each_corner_drag_and_saved_proportions(self):
        for sx,sy in ((-1,-1),(1,-1),(-1,1),(1,1)):
            self.editor.load('',[encode_image(self.source)])
            name=next(iter(self.editor.items));canvas=self.editor.items[name]['canvas']
            self.root.update()
            x=6 if sx<0 else 406;y=6 if sy<0 else 206
            canvas.event_generate('<Button-1>',x=x,y=y)
            self.root.update()
            canvas.event_generate('<B1-Motion>',x=x-80*sx,y=y-40*sy)
            self.root.update()
            canvas.event_generate('<ButtonRelease-1>',x=x-80*sx,y=y-40*sy)
            self.root.update()
            self.assertEqual(self.editor.items[name]['size'],(320,160))
            self.assertEqual(self.editor.serialize()[1][0]['width'],320)
            self.assertIsNone(self.editor.drag)

    def test_roundtrip_unicode_responsive_and_delete(self):
        content='Début 🐧\nFin\n';images=[dict(encode_image(self.source),offset=8)]
        self.editor.load(content,images);self.root.update()
        self.assertEqual(self.editor.serialize(),(content,images))
        self.root.geometry('250x500');self.root.update();self.editor.refresh()
        self.assertLess(next(iter(self.editor.items.values()))['size'][0],250)
        self.assertEqual(self.editor.serialize(),(content,images))
        name=next(iter(self.editor.items));self.editor.select(name)
        self.text.delete(name);self.root.update()
        self.assertIsNone(self.editor.selected);self.assertEqual(self.editor.serialize(),(content,[]))

    def test_persistence_and_validation(self):
        article=dict(id='1',title='Capture',system='Tous',category='',keywords='',content='',images=[encode_image(self.source)])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'documentation.json';save_articles(path,[article])
            self.assertEqual(load_articles(path),[article])
        for changes in ({'width':False},{'offset':1},{'data':'invalid'}):
            with self.assertRaises(ValueError):validate_images(dict(article,images=[dict(article['images'][0],**changes)]))


class ImageEditorIntegrationTest(unittest.TestCase):
    def test_save_reader_reopen_and_cancel(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'documentation.json'
            with patch.object(ndt,'DOCUMENTATION_FILE',path),patch.object(ndt,'SETTINGS_FILE',Path(folder)/'settings.json'):
                app=ndt.App(session=droits.session_bypass());app.attributes('-alpha',0)
                try:
                    app.session_user='coordinateur';app.show_admin();app.documentation_editor.edit_article()
                    win=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
                    win.attributes('-alpha',0);win.geometry('640x600');app.update()
                    next(w for w in descendants(win) if type(w)==ttk.Entry).insert(0,'Capture')
                    with patch('article_images.ImageGrab.grabclipboard',return_value=Image.new('RGB',(300,150),'red')):win.image_editor.paste()
                    save=next(w for w in descendants(win) if isinstance(w,ttk.Button) and w.cget('text')=='Enregistrer l’article')
                    self.assertGreater(win.image_editor.text.winfo_height(),80)
                    self.assertLessEqual(save.winfo_rooty()+save.winfo_height(),win.winfo_rooty()+win.winfo_height())
                    save.invoke();saved=load_articles(path)[0]
                    self.assertEqual(len(saved['images']),1)
                    app.show_documentation();app.update()
                    self.assertEqual(len(app.documentation.content.window_names()),1)
                    self.assertEqual(app.documentation.content.cget('state'),'disabled')
                    app.session_user='coordinateur';app.show_admin();app.documentation_editor.edit_article(saved)
                    win=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
                    editor=win.image_editor;editor.select(next(iter(editor.items)));editor.remove_image()
                    with patch.object(app,'confirm',return_value=True):
                        next(w for w in descendants(win) if isinstance(w,ttk.Button) and w.cget('text')=='Annuler').invoke()
                    self.assertEqual(load_articles(path),[saved])
                finally:app.destroy()


if __name__=='__main__':unittest.main()
