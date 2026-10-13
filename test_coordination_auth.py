import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from coordination_auth import save_coordinateur_password, verify_coordinateur
from test_routes import ndt


class CoordinationAuthTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'auth.json'
        self.addCleanup(self.temp.cleanup)

    def test_initial_password(self):
        self.assertTrue(verify_coordinateur(self.path,'initial','initial'))
        self.assertFalse(verify_coordinateur(self.path,'wrong','initial'))

    def test_changed_password_overrides_code_default_and_survives_reload(self):
        save_coordinateur_password(self.path,'nouveau-é-123')
        self.assertTrue(verify_coordinateur(self.path,'nouveau-é-123','initial'))
        self.assertFalse(verify_coordinateur(self.path,'initial','initial'))
        self.assertNotIn('nouveau-é-123',self.path.read_text())

    def test_admin_independent_of_coordinateur(self):
        with patch.object(ndt,'AUTH_FILE',self.path):
            save_coordinateur_password(self.path,'updated')
            self.assertTrue(ndt.App.authenticate(None,'admin',ndt.ADMIN_PASSWORD))
            self.assertFalse(ndt.App.authenticate(None,'admin','updated'))
            self.assertTrue(ndt.App.authenticate(None,'coordinateur','updated'))
            self.assertFalse(ndt.App.authenticate(None,'unknown','updated'))

    def test_corrupt_file_does_not_restore_default(self):
        self.path.write_text('{}')
        with self.assertRaises(ValueError):verify_coordinateur(self.path,'initial','initial')

    def test_failed_write_preserves_previous_password(self):
        save_coordinateur_password(self.path,'previous')
        with patch('coordination_auth.os.replace',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):save_coordinateur_password(self.path,'new')
        self.assertTrue(verify_coordinateur(self.path,'previous','initial'))


if __name__=='__main__':unittest.main()
