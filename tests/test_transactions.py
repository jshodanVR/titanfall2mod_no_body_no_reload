"""Installation/recovery tests use synthetic bytes, never original game assets."""
from pathlib import Path
import copy, json, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import patcher

class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)
        self.original = b'synthetic original dll'
        self.patched = b'synthetic patched dll'
        self.config = copy.deepcopy(patcher.CONFIG)
        self.config['dll_original_sha256'] = patcher.digest(self.original)
        self.config['dll_patched_sha256'] = patcher.digest(self.patched)
        (self.game / patcher.DLL).parent.mkdir(parents=True)
        (self.game / patcher.DLL).write_bytes(self.original)
        self.files = {str(patcher.DLL): self.patched,
                      str(patcher.MOD / 'mod.json'): patcher.make_mod_json(self.config)}
        self.files.update({str(patcher.MOD/patcher.MODEL_PATH/n):('synthetic '+n).encode() for n in self.config['models']})

    def install(self):
        patcher.install_prepared(self.game, self.files, self.original, self.config)

    def test_round_trip_and_reinstall(self):
        self.install()
        for name, value in self.files.items(): self.assertEqual((self.game/name).read_bytes(), value)
        patcher.uninstall(self.game, self.config)
        self.assertEqual((self.game/patcher.DLL).read_bytes(), self.original)
        self.assertFalse((self.game/patcher.MOD).exists())
        self.install()
        self.assertEqual((self.game/patcher.DLL).read_bytes(), self.patched)

    def test_later_model_edit_blocks_restore_before_any_change(self):
        self.install()
        model = next(p for p in self.files if p.endswith('.mdl'))
        (self.game/model).write_bytes(b'later user edit')
        with self.assertRaisesRegex(ValueError, 'File changed'):
            patcher.uninstall(self.game, self.config)
        self.assertEqual((self.game/patcher.DLL).read_bytes(), self.patched)
        self.assertTrue((self.game/patcher.MOD/'mod.json').is_file())

    def test_corrupt_backup_does_not_touch_installation(self):
        self.install()
        (self.game/patcher.BACKUP/'original.dll').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'backup is invalid'):
            patcher.uninstall(self.game, self.config)
        self.assertEqual((self.game/patcher.DLL).read_bytes(), self.patched)

    def test_existing_mod_folder_is_preserved(self):
        (self.game/patcher.MOD).mkdir(parents=True)
        marker=self.game/patcher.MOD/'user.txt';marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'): self.install()
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual((self.game/patcher.DLL).read_bytes(), self.original)

    def test_interrupted_install_can_be_recovered(self):
        self.install()
        receipt=self.game/patcher.BACKUP/'receipt.json'
        data=json.loads(receipt.read_text());data['state']='prepared';receipt.write_text(json.dumps(data))
        model=next(p for p in self.files if p.endswith('.mdl'));(self.game/model).unlink()
        patcher.uninstall(self.game,self.config)
        self.assertEqual((self.game/patcher.DLL).read_bytes(),self.original)

    def test_write_failure_rolls_back(self):
        real_write=patcher.atomic_write
        failed=False
        def fail_once(path,data):
            nonlocal failed
            if not failed and path.suffix=='.mdl':
                failed=True
                raise OSError('simulated write error')
            real_write(path,data)
        with patch.object(patcher,'atomic_write',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'simulated'):self.install()
        self.assertEqual((self.game/patcher.DLL).read_bytes(),self.original)
        self.assertFalse((self.game/patcher.MOD).exists())

    def test_invalid_receipt_paths_are_rejected(self):
        self.install()
        receipt=self.game/patcher.BACKUP/'receipt.json';data=json.loads(receipt.read_text())
        data['files']['../../unrelated.txt']='fake';receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Invalid recovery receipt'):
            patcher.uninstall(self.game,self.config)
        self.assertEqual((self.game/patcher.DLL).read_bytes(),self.patched)

    def test_unknown_dll_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            patcher.patch_dll(b'wrong version')

    def test_base_mod_version_is_separate_from_installer_version(self):
        (self.game/'Titanfall2.exe').write_bytes(b'synthetic')
        meta=self.game/'.circuitlord-vr-mods/Titanfall2VR.json';meta.parent.mkdir()
        meta.write_text(json.dumps({'version':'1.2.12'}))
        with self.assertRaisesRegex(ValueError,'1.0.25'):patcher.validate_game(self.game)
        meta.write_text(json.dumps({'version':'1.0.25'}))
        patcher.validate_game(self.game)

if __name__=='__main__':unittest.main()
