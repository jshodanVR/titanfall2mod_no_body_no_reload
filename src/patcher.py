"""Local-only patch generator. No game/mod binaries or meshes are distributed."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, struct, subprocess, sys, tempfile

PROJECT = 'titanfall2mod_no_body_no_reload'
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / 'compatibility.json').read_text(encoding='utf-8-sig'))
DLL = Path('TF2VR/plugins/Titanfall2VR.dll')
MOD = Path('TF2VR/mods') / PROJECT
BACKUP = Path('TF2VR') / (PROJECT + '.backup')
MODEL_PATH = Path('mod/models/weapons/arms')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.patch-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def allowed_targets(config=CONFIG):
    return {str(DLL), str(MOD / 'mod.json')} | {str(MOD / MODEL_PATH / n) for n in config['models']}

def validate_game(game, config=CONFIG):
    if not any((game / exe).is_file() for exe in ('Titanfall2.exe', 'Titanfall2_trial.exe')):
        raise ValueError('Select the Titanfall 2 folder containing Titanfall2.exe.')
    manifest = game / '.circuitlord-vr-mods/Titanfall2VR.json'
    if not manifest.is_file():
        raise ValueError('Install the base CircuitLord Titanfall2VR mod first, using its official installer.')
    record = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if str(record.get('version')) != config['required_mod_version']:
        raise ValueError('Required BASE MOD: CircuitLord Titanfall2VR 1.0.25 (not the installer version).')
    if not (game / DLL).is_file():
        raise ValueError('The base mod TF2VR/plugins/Titanfall2VR.dll is missing.')

def patch_dll(original, config=CONFIG):
    if digest(original) != config['dll_original_sha256']:
        raise ValueError('Unsupported or already modified VR DLL. Only the exact Titanfall2VR 1.0.25 build is supported.')
    result = bytearray(original)
    for call in config['reload_calls']:
        offset = call['file_offset']
        if original[offset] != 0xE8 or call['rva'] + 5 + struct.unpack_from('<i', original, offset+1)[0] != call['target_rva']:
            raise ValueError('Unexpected reload instruction; no patch applied.')
        result[offset:offset+5] = bytes.fromhex('31 c0 90 90 90')
    if digest(result) != config['dll_patched_sha256']:
        raise ValueError('The generated DLL did not match the validated result.')
    return bytes(result)

def run(command):
    p = subprocess.run(command, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-6000:])

def generate_models(originals, config=CONFIG):
    for name, data in originals.items():
        if digest(data) != config['models'][name]['original_sha256']:
            raise ValueError('Unsupported original game model: ' + name)
    with tempfile.TemporaryDirectory(prefix='tf2p-') as temp:
        work = Path(temp)
        for name, data in originals.items(): (work / name).write_bytes(data)
        for script in ('build_hands_models.py', 'cap_wrist_models.py', 'refine_cuffs.py'):
            shutil.copy2(ROOT / 'src' / script, work / script)
            run([sys.executable, str(work / script)])
        result = {}
        for name, entry in config['models'].items():
            data = (work / 'hands_refined' / 'generated' / MODEL_PATH / name).read_bytes()
            if digest(data) != entry['patched_sha256']:
                raise ValueError('Generated model differs from the tested result: ' + name)
            result[str(MOD / MODEL_PATH / name)] = data
        return result

def make_mod_json(config=CONFIG):
    return (json.dumps({'Name': PROJECT, 'Description': 'Hands only with closed cuffs; automatic game reload.',
                       'Version': config['version'], 'LoadPriority': 100, 'RequiredOnClient': False}, indent=2)+'\n').encode()

def install_prepared(game, prepared, original_dll, config=CONFIG):
    if set(prepared) != allowed_targets(config): raise ValueError('Unexpected installation targets.')
    if digest(original_dll) != config['dll_original_sha256']: raise ValueError('Original backup does not match.')
    if (game / MOD).exists(): raise ValueError('The add-on folder already exists; uninstall the previous add-on first.')
    receipt_path = game / BACKUP / 'receipt.json'
    if receipt_path.exists():
        old = json.loads(receipt_path.read_text())
        if old.get('state') != 'uninstalled': raise ValueError('An installation or recovery receipt already exists. Run Uninstall first.')
    backup_file = game / BACKUP / 'original.dll'
    if backup_file.exists() and digest(backup_file.read_bytes()) != config['dll_original_sha256']:
        raise ValueError('A different backup exists; it will not be overwritten.')
    if digest((game / DLL).read_bytes()) != config['dll_original_sha256']:
        raise ValueError('The installed DLL changed during preparation.')
    atomic_write(backup_file, original_dll)
    receipt = {'project': PROJECT, 'version': config['version'], 'state': 'prepared',
               'files': {p: digest(b) for p,b in prepared.items()}}
    atomic_write(receipt_path, json.dumps(receipt, indent=2).encode())
    try:
        # Register a recovery receipt before touching the game. Backups stay local.
        for relative, data in sorted(prepared.items(), key=lambda item: item[0] == str(DLL)):
            atomic_write(game / relative, data)
            if digest((game / relative).read_bytes()) != receipt['files'][relative]:
                raise ValueError('Installation verification failed: ' + relative)
        receipt['state'] = 'installed'
        atomic_write(receipt_path, json.dumps(receipt, indent=2).encode())
    except Exception:
        uninstall(game, config)
        raise

def uninstall(game, config=CONFIG):
    receipt_path = game / BACKUP / 'receipt.json'
    if not receipt_path.is_file(): raise ValueError('No installation receipt was found for this add-on.')
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('project') != PROJECT or set(receipt.get('files', {})) != allowed_targets(config):
        raise ValueError('Invalid recovery receipt. No files changed.')
    if receipt.get('state') == 'uninstalled': return
    backup = (game / BACKUP / 'original.dll').read_bytes()
    if digest(backup) != config['dll_original_sha256']: raise ValueError('Original DLL backup is invalid.')
    # Preflight every target before making any changes: refuse later edits/updates.
    for relative, expected in receipt['files'].items():
        path = game / relative
        if path.exists():
            permitted = {expected}
            if relative == str(DLL): permitted.add(config['dll_original_sha256'])
            if digest(path.read_bytes()) not in permitted:
                raise ValueError('File changed after installation; restore cancelled: ' + relative)
    atomic_write(game / DLL, backup)
    for relative in receipt['files']:
        if relative != str(DLL): (game / relative).unlink(missing_ok=True)
    # Remove empty directories only; never recursively remove user files.
    for directory in (game / MOD / MODEL_PATH, game / MOD / 'mod/models/weapons',
                      game / MOD / 'mod/models', game / MOD / 'mod', game / MOD):
        try: directory.rmdir()
        except OSError: pass
    receipt['state'] = 'uninstalled'
    atomic_write(receipt_path, json.dumps(receipt, indent=2).encode())

def main():
    p = argparse.ArgumentParser(description=PROJECT)
    p.add_argument('action', choices=['check', 'install', 'uninstall'])
    p.add_argument('--game', required=True, type=Path)
    p.add_argument('--node', type=Path)
    p.add_argument('--vpk-library', type=Path)
    args = p.parse_args(); game = args.game.expanduser().resolve()
    if args.action == 'uninstall':
        uninstall(game); print('Add-on removed. Original VR DLL restored.'); return
    validate_game(game)
    receipt_path = game / BACKUP / 'receipt.json'
    if receipt_path.exists() and json.loads(receipt_path.read_text()).get('state') == 'installed':
        receipt = json.loads(receipt_path.read_text())
        if set(receipt.get('files', {})) != allowed_targets(): raise ValueError('Invalid installation receipt.')
        if all((game / name).is_file() and digest((game / name).read_bytes()) == value for name,value in receipt['files'].items()):
            print('This add-on is already installed and all files match.'); return
        raise ValueError('An installed file changed; run Uninstall before proceeding.')
    original = (game / DLL).read_bytes(); patched = patch_dll(original)
    if args.action == 'check': print('Compatible base mod: Titanfall2VR 1.0.25; exact DLL verified.'); return
    if not args.node or not args.vpk_library: raise ValueError('Node and the VPK reader paths are required by the installer.')
    with tempfile.TemporaryDirectory(prefix='tf2p-extract-') as temp:
        run([str(args.node), str(ROOT/'src/read_models.cjs'), str(game/'vpk'), temp, str(args.vpk_library.resolve())])
        originals = {n:(Path(temp)/n).read_bytes() for n in CONFIG['models']}
        prepared = generate_models(originals)
    prepared[str(DLL)] = patched; prepared[str(MOD/'mod.json')] = make_mod_json()
    install_prepared(game, prepared, original)
    print('Installed: automatic game reload and hands-only models with closed, refined wrists.')
    print('Local backup: ' + str(game / BACKUP))

if __name__ == '__main__':
    try: main()
    except (Exception, KeyboardInterrupt) as exc:
        print('STOP: '+str(exc), file=sys.stderr); sys.exit(1)
