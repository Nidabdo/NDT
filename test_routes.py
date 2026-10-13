import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ndt", Path(__file__).with_name("NDT v1.py"))
ndt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ndt)


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.questions = ndt.normalize([
            dict(id="os", text="Système", tag="os", type="choice",
                 choices=["Linux", "Windows"], routes=["linux", "windows"]),
            dict(id="linux", text="Distribution Linux", tag="linux", type="free", next="common"),
            dict(id="windows", text="Version Windows", tag="windows", type="free", next="common"),
            dict(id="common", text="Problème", tag="problem", type="free", next="__END__"),
        ])

    def test_separate_branches(self):
        self.assertEqual(ndt.next_index(self.questions, 0, 0, [0]), 1)
        self.assertEqual(ndt.next_index(self.questions, 0, 1, [0]), 2)

    def test_free_answer_joins_common_question(self):
        self.assertEqual(ndt.next_index(self.questions, 1, "Ubuntu", [0, 1]), 3)
        self.assertEqual(ndt.next_index(self.questions, 2, "11", [0, 2]), 3)

    def test_explicit_and_implicit_end(self):
        self.assertIsNone(ndt.next_index(self.questions, 3, "Réseau", [0, 1, 3]))
        self.questions[3]["next"] = ""
        self.assertIsNone(ndt.next_index(self.questions, 3, "Réseau", [0, 2, 3]))

    def test_optional_skip(self):
        self.questions[0]["next"] = "common"
        self.assertEqual(ndt.next_index(self.questions, 0, None, [0]), 3)

    def test_old_sequential_data(self):
        self.questions[0]["routes"] = ["", ""]
        self.assertEqual(ndt.next_index(self.questions, 0, 0, [0]), 1)

    def test_missing_target_and_cycle(self):
        for target in ["missing", "os"]:
            self.questions[1]["next"] = target
            with self.assertRaises(ValueError):
                ndt.next_index(self.questions, 1, "Ubuntu", [0, 1])

    def test_routes_follow_reordered_choices(self):
        self.assertEqual(ndt.align_routes(["Linux", "Windows"], ["linux", "windows"],
                                         ["Windows", "Other", "Linux"]), ["windows", "", "linux"])

    def test_storage_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ndt, "DATA_FILE", Path(directory) / "questions.json"):
                ndt.save_data(self.questions, "{reponses}")
                data = ndt.load_data()
                self.assertEqual(data["questions"], self.questions)

    def test_result_only_contains_visited_branch(self):
        app = SimpleNamespace(questions=self.questions, history=[0, 2, 3],
                              answers={0: 1, 1: "stale Ubuntu", 2: "11", 3: "Réseau"}, template="")
        app.answer_text = lambda i: ndt.App.answer_text(app, i)
        result = ndt.App.build_result_text(app)
        self.assertIn("Windows", result)
        self.assertNotIn("Linux", result)
        self.assertNotIn("stale", result)
        app.template = "{linux} / {windows}"
        self.assertEqual(ndt.App.build_result_text(app), " / 11")

    def test_empty_answers_are_omitted_from_summary(self):
        app = SimpleNamespace(questions=self.questions, history=[0, 2, 3],
                              answers={0: 1, 2: '11'}, template='')
        app.answer_text = lambda i: ndt.App.answer_text(app, i)
        result = ndt.App.build_result_text(app)
        self.assertNotIn('Problème', result)
        self.assertNotIn('non renseigné', result)
        self.assertIn('2. Version Windows', result)
        app.template = '{linux}{problem}'
        self.assertEqual(ndt.App.build_result_text(app), '')

    def test_back_removes_abandoned_answer(self):
        app = SimpleNamespace(history=[0, 1], current=1, answers={0: 0, 1: "Ubuntu"},
                              store_current=lambda: None, show_question=lambda: None)
        ndt.App.prev_question(app)
        self.assertEqual(app.history, [0])
        self.assertEqual(app.answers, {0: 0})
        self.assertEqual(app.current, 0)

    def test_form_restores_routes_and_clears_new_question(self):
        class Field:
            def delete(self, *args): pass
            def insert(self, *args): pass
            def set(self, *args): pass
            def configure(self, **kwargs): pass
        app = SimpleNamespace(q_entry=Field(), tag_entry=Field(), type_var=Field(),
                              req_var=Field(), c_text=Field(), update_type=lambda: None)
        ndt.App.fill_form(app, self.questions[0])
        self.assertEqual(app.form_routes, ["linux", "windows"])
        ndt.App.fill_form(app, self.questions[1])
        self.assertEqual(app.form_next, "common")
        ndt.App.fill_form(app)
        self.assertEqual(app.form_routes, [])
        self.assertEqual(app.form_next, "")


if __name__ == "__main__":
    unittest.main()
