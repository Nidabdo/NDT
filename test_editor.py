import unittest
from parcours_editor import reordered, validate_links


class EditorTest(unittest.TestCase):
    def test_reorder_keeps_explicit_links(self):
        questions = [dict(id='start', type='choice', choices=['Linux','Windows'], routes=['linux','windows']),
                     dict(id='linux', type='free', next='__END__'),
                     dict(id='windows', type='free', next='__END__')]
        result = reordered(questions, 1, 2)
        self.assertEqual([q['id'] for q in result], ['start','windows','linux'])
        self.assertEqual(result[0]['routes'], ['linux','windows'])
        self.assertEqual(questions[1]['id'], 'linux')

    def test_reorder_rejects_new_implicit_cycle(self):
        questions = [dict(id='a',type='free',next='b'),dict(id='b',type='free',next='')]
        with self.assertRaises(ValueError): reordered(questions,0,1)

    def test_rejects_missing_targets_and_cycles(self):
        for destination in ['missing','a']:
            with self.assertRaises(ValueError):
                validate_links([dict(id='a',type='free',next=destination)])

    def test_allows_common_branch(self):
        validate_links([dict(id='a',type='choice',routes=['b','c']),dict(id='b',type='free',next='d'),
                        dict(id='c',type='free',next='d'),dict(id='d',type='free',next='__END__')])


if __name__ == '__main__': unittest.main()
