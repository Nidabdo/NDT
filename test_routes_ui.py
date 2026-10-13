"""Vérification avec les vrais widgets, sur des données temporaires isolées."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch
from test_routes import ndt, RoutesTest


def children(widget):
    for child in widget.winfo_children():
        yield child
        yield from children(child)


class RouteUITest(unittest.TestCase):
    def test_result_actions_stay_inside_small_window(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ndt,'SETTINGS_FILE',Path(directory)/'settings.json'):
                app=ndt.App()
                app.attributes('-alpha',0)
                try:
                    app.questions=ndt.normalize([dict(id='q',text='Description',type='free')])
                    app.answers={0:'Une description très longue.\n'*200}
                    app.history=[0]
                    for theme in ('light','dark'):
                        app.theme=theme;app.p=ndt.PALETTES[theme];app.apply_theme()
                        app.show_result()
                        for width,height in [(1180,800),(800,600)]:
                            app.geometry(f'{width}x{height}')
                            app.update()
                            app.update_idletasks()
                            for button in app.result_buttons:
                                self.assertGreater(button.winfo_height(),30)
                                x=button.winfo_rootx()-app.winfo_rootx()
                                y=button.winfo_rooty()-app.winfo_rooty()
                                self.assertGreaterEqual(x,0)
                                self.assertGreaterEqual(y,0)
                                self.assertLessEqual(x+button.winfo_width(),app.winfo_width())
                                self.assertLessEqual(y+button.winfo_height(),app.winfo_height())
                                self.assertEqual(app.style.lookup(button.cget('style'),'background'),app.p['surface'])
                                self.assertEqual(app.style.lookup(button.cget('style'),'background',('active',)),app.p['surface'])
                finally:app.destroy()

    def test_six_fields_fit_typical_form_heights(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ndt, 'SETTINGS_FILE', Path(directory) / 'settings.json'):
                app=ndt.App();app.withdraw()
                try:
                    app.questions=ndt.normalize([
                        dict(id='os',text='Poste',type='choice',choices=['Linux','Windows'])
                    ]+[dict(id=str(i),text='Problématique / Comment le problème se produit' if i==3 else 'Question '+str(i),type='free') for i in range(1,7)])
                    app.answers={0:0};app.skipped=set();app.show_form()
                    app.update_idletasks()
                    for width,height in [(1200,650),(850,500),(640,420)]:
                        with patch.object(app.form.canvas,'winfo_width',return_value=width), patch.object(app.form.canvas,'winfo_height',return_value=height):
                            app.form.reflow()
                            app.update_idletasks()
                            self.assertLessEqual(app.form.rows.winfo_reqheight(),height)
                            self.assertFalse(app.form.scrollbar.winfo_manager())
                    with patch.object(app.form.canvas,'winfo_width',return_value=450), patch.object(app.form.canvas,'winfo_height',return_value=300):
                        app.form.reflow();app.update_idletasks()
                        self.assertEqual(app.form.row_widgets[0][1].grid_info()['column'],0)
                        self.assertTrue(app.form.scrollbar.winfo_manager())
                finally:app.destroy()

    def test_edit_save_reload_and_run_both_branches(self):
        fixture = RoutesTest()
        fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ndt, "DATA_FILE", Path(directory) / "questions.json"), \
                 patch.object(ndt, "SETTINGS_FILE", Path(directory) / "settings.json"):
                ndt.save_data(fixture.questions, "{reponses}")
                app = ndt.App()
                app.withdraw()
                try:
                    app.questions = ndt.load_data()["questions"]
                    app.template = "{reponses}"
                    app.show_admin()
                    editor = app.parcours_editor
                    editor.selected_id = 'os'
                    editor.choose_target(0, 0)
                    win = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
                    win.withdraw()
                    fields = [w for w in children(win) if isinstance(w, ttk.Combobox)]
                    self.assertIn("Distribution Linux", fields[0].get())
                    save = next(w for w in children(win) if isinstance(w, ttk.Button)
                                and w.cget("text") == "Relier les questions")
                    save.invoke()
                    self.assertFalse(win.winfo_exists())
                    self.assertEqual(ndt.load_data()["questions"][0]["routes"], ["linux", "windows"])
                    editor.reorder(1, 2)
                    self.assertEqual(app.questions[2]['id'], 'linux')
                    self.assertEqual(app.questions[0]['routes'], ['linux', 'windows'])
                    editor.reorder(2, 1)
                    editor.selected_id = 'linux'
                    editor.edit()
                    form = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
                    form.withdraw()
                    title = next(w for w in children(form) if isinstance(w, ttk.Entry))
                    title.delete(0, 'end')
                    title.insert(0, 'Distribution Linux modifiée')
                    next(w for w in children(form) if isinstance(w, ttk.Button)
                         and w.cget('text') == 'Enregistrer le bloc').invoke()
                    self.assertEqual(app.questions[1]['tag'], 'linux')
                    self.assertEqual(app.questions[1]['next'], 'common')
                    for answer, target, version in [(0, 1, "Ubuntu"), (1, 2, "11")]:
                        app.start_user()
                        app.choice_var.set(answer)
                        app.next_question()
                        self.assertEqual(app.current, target)
                        self.assertEqual(app.mode, 'form')
                        self.assertEqual(set(app.form.fields), {target,3})
                        with patch.object(app, 'warn') as warn:
                            app.form.finish()
                            warn.assert_called_once()
                            self.assertEqual(app.mode, 'form')
                        app.form.fields[target].insert("1.0", version)
                        app.form.fields[3].insert("1.0", "Réseau")
                        app.toggle_theme()
                        app.form.finish()
                        self.assertIn(version, app.result_text)
                        self.assertNotIn("Version Windows" if answer == 0 else "Distribution Linux", app.result_text)
                        app.show_form()
                        self.assertEqual(app.form.fields[target].get('1.0','end').strip(), version)
                    app.form.change_root()
                    app.choice_var.set(0)
                    app.next_question()
                    self.assertEqual(set(app.form.fields), {1,3})
                    self.assertNotIn(2, app.answers)
                    self.assertEqual(app.answers[3], 'Réseau')
                    app.show_home()
                    labels = [str(w.cget('text')) for w in children(app) if isinstance(w, (ttk.Button, ttk.Label))]
                    self.assertNotIn('Parcours', labels)
                    self.assertNotIn('Configurer  →', labels)
                    self.assertNotIn('admin', app.nav_buttons)
                    self.assertTrue(app.bind('<Control-Shift-A>'))
                finally:
                    app.destroy()


if __name__ == "__main__":
    unittest.main()
