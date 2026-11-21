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

def build_config(version, config=CONFIG):
    profiles = config.get('supported_builds', {})
    if profiles:
        if version not in profiles:
            raise ValueError('Supported stable BASE MOD versions: ' + ', '.join(profiles) + ' (not installer versions).')
        return dict(config, **profiles[version], required_mod_version=version)
    if version != config['required_mod_version']:
        raise ValueError('Required BASE MOD: Titanfall2VR ' + config['required_mod_version'])
    return config

def backup_config(backup, config=CONFIG):
    if digest(backup) == config['dll_original_sha256']: return config
    for version in config.get('supported_builds', {}):
        candidate = build_config(version, config)
        if digest(backup) == candidate['dll_original_sha256']: return candidate
    raise ValueError('Original DLL backup is invalid.')

def remove_empty_mod_dirs(game):
    for directory in (game / MOD / MODEL_PATH, game / MOD / 'mod/models/weapons',
                      game / MOD / 'mod/models', game / MOD / 'mod', game / MOD):
        try: directory.rmdir()
        except OSError: pass

def validate_game(game, config=CONFIG):
    if not any((game / exe).is_file() for exe in ('Titanfall2.exe', 'Titanfall2_trial.exe')):
        raise ValueError('Select the Titanfall 2 folder containing Titanfall2.exe.')
    manifest = game / '.circuitlord-vr-mods/Titanfall2VR.json'
    if not manifest.is_file():
        raise ValueError('Install the base CircuitLord Titanfall2VR mod first, using its official installer.')
    record = json.loads(manifest.read_text(encoding='utf-8-sig'))
    selected = build_config(str(record.get('version')), config)
    if not (game / DLL).is_file():
        raise ValueError('The base mod TF2VR/plugins/Titanfall2VR.dll is missing.')
    return selected

def patch_dll(original, config=CONFIG):
    if digest(original) != config['dll_original_sha256']:
        raise ValueError('Unsupported or already modified VR DLL for Titanfall2VR ' + config['required_mod_version'] + '.')
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
    receipt_path = game / BACKUP / 'receipt.json'
    previous_receipt = receipt_path.read_bytes() if receipt_path.exists() else None
    owned_install = False
    if receipt_path.exists():
        old = json.loads(receipt_path.read_text())
        if old.get('project') != PROJECT or set(old.get('files', {})) != allowed_targets(config):
            raise ValueError('Invalid existing installation receipt.')
        if old.get('state') == 'installed':
            for relative, expected in old['files'].items():
                if relative == str(DLL): continue
                path = game / relative
                if not path.is_file() or digest(path.read_bytes()) != expected:
                    raise ValueError('Existing add-on file changed; upgrade cancelled: ' + relative)
            owned_install = True
        elif old.get('state') != 'uninstalled':
            raise ValueError('An incomplete recovery receipt exists. Run Uninstall first.')
    if (game / MOD).exists() and not owned_install:
        raise ValueError('The add-on folder already exists and is not owned by a valid installation receipt.')
    backup_file = game / BACKUP / 'original.dll'
    previous_backup = backup_file.read_bytes() if backup_file.exists() else None
    if previous_backup is not None and digest(previous_backup) != config['dll_original_sha256']:
        previous_config = backup_config(previous_backup, config)
        archive = game / BACKUP / ('original-' + previous_config['required_mod_version'] + '.dll')
        if archive.exists() and archive.read_bytes() != previous_backup:
            raise ValueError('A different archived backup exists; it will not be overwritten.')
        atomic_write(archive, previous_backup)
    if digest((game / DLL).read_bytes()) != config['dll_original_sha256']:
        raise ValueError('The installed DLL changed during preparation.')
    previous_targets = {p:(game / p).read_bytes() if (game / p).exists() else None for p in prepared}
    atomic_write(backup_file, original_dll)
    receipt = {'project': PROJECT, 'version': config['version'], 'base_mod_version':config['required_mod_version'], 'state': 'prepared',
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
        for relative, previous in previous_targets.items():
            if previous is None: (game / relative).unlink(missing_ok=True)
            else: atomic_write(game / relative, previous)
        if previous_backup is not None: atomic_write(backup_file, previous_backup)
        if previous_receipt is not None: atomic_write(receipt_path, previous_receipt)
        else:
            receipt['state'] = 'uninstalled'
            atomic_write(receipt_path, json.dumps(receipt, indent=2).encode())
        remove_empty_mod_dirs(game)
        raise

def uninstall(game, config=CONFIG):
    receipt_path = game / BACKUP / 'receipt.json'
    if not receipt_path.is_file(): raise ValueError('No installation receipt was found for this add-on.')
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('project') != PROJECT or set(receipt.get('files', {})) != allowed_targets(config):
        raise ValueError('Invalid recovery receipt. No files changed.')
    if receipt.get('state') == 'uninstalled': return
    backup = (game / BACKUP / 'original.dll').read_bytes()
    config = backup_config(backup, config)
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
    remove_empty_mod_dirs(game)
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
    config = validate_game(game)
    receipt_path = game / BACKUP / 'receipt.json'
    if receipt_path.exists() and json.loads(receipt_path.read_text()).get('state') == 'installed':
        receipt = json.loads(receipt_path.read_text())
        if set(receipt.get('files', {})) != allowed_targets(): raise ValueError('Invalid installation receipt.')
        if (digest((game / DLL).read_bytes()) == config['dll_patched_sha256'] and
            all((game / name).is_file() and digest((game / name).read_bytes()) == value for name,value in receipt['files'].items())):
            print('This add-on is already installed and all files match.'); return
        if digest((game / DLL).read_bytes()) != config['dll_original_sha256']:
            raise ValueError('An installed file changed; no automatic upgrade can be applied.')
    original = (game / DLL).read_bytes(); patched = patch_dll(original, config)
    if args.action == 'check': print('Compatible base mod: Titanfall2VR ' + config['required_mod_version'] + '; exact DLL verified.'); return
    if not args.node or not args.vpk_library: raise ValueError('Node and the VPK reader paths are required by the installer.')
    with tempfile.TemporaryDirectory(prefix='tf2p-extract-') as temp:
        run([str(args.node), str(ROOT/'src/read_models.cjs'), str(game/'vpk'), temp, str(args.vpk_library.resolve())])
        originals = {n:(Path(temp)/n).read_bytes() for n in CONFIG['models']}
        prepared = generate_models(originals, config)
    prepared[str(DLL)] = patched; prepared[str(MOD/'mod.json')] = make_mod_json(config)
    install_prepared(game, prepared, original, config)
    print('Installed: automatic game reload and hands-only models with closed, refined wrists.')
    print('Local backup: ' + str(game / BACKUP))

if __name__ == '__main__':
    try: main()
    except (Exception, KeyboardInterrupt) as exc:
        print('STOP: '+str(exc), file=sys.stderr); sys.exit(1)
