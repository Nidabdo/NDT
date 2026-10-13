import unittest
from diagnostic_form import visible_path
from test_routes import ndt


class FormPathTest(unittest.TestCase):
    def setUp(self):
        self.q=ndt.normalize([
            dict(id='os',type='choice',choices=['Linux','Windows'],routes=['linux','windows']),
            dict(id='linux',type='free',next='common'),
            dict(id='windows',type='free',next='common'),
            dict(id='common',type='choice',choices=['Oui','Non'],routes=['detail','__END__'],required=False),
            dict(id='detail',type='free',next='__END__')])

    def test_linux_and_windows_fields(self):
        self.assertEqual(visible_path(self.q,{0:0},ndt.next_index),[0,1,3])
        self.assertEqual(visible_path(self.q,{0:1},ndt.next_index),[0,2,3])

    def test_conditional_fields(self):
        self.assertEqual(visible_path(self.q,{0:0,3:0},ndt.next_index),[0,1,3,4])
        self.assertEqual(visible_path(self.q,{0:0,3:1},ndt.next_index),[0,1,3])

    def test_explicit_optional_skip(self):
        self.assertEqual(visible_path(self.q,{0:0},ndt.next_index,{3}),[0,1,3,4])

    def test_shared_destinations_do_not_hide_following_fields(self):
        self.q[3]['routes']=['detail','detail']
        self.assertEqual(visible_path(self.q,{0:1},ndt.next_index),[0,2,3,4])


if __name__=='__main__':unittest.main()
