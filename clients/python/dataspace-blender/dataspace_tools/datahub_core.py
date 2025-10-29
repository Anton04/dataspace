# datahub_core.py
import os, sys, subprocess, importlib, pathlib, json
import bpy

# --- Directories ---
_ADDON_DIR = pathlib.Path(__file__).parent
_LIBS_DIR = _ADDON_DIR / "libs"
os.makedirs(_LIBS_DIR, exist_ok=True)
if str(_LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(_LIBS_DIR))

# --- Dependency handling for dataspace_client ---
def _install_dataspace_client(upgrade=True):
    import sys, subprocess, importlib
    py = sys.executable
    libs = _LIBS_DIR
    try:
        subprocess.check_call([py, "-m", "ensurepip", "--upgrade"])
    except Exception:
        pass

    cmd = [py, "-m", "pip", "install", "dataspace_client", "-t", str(libs)]
    if upgrade:
        cmd.insert(4, "--upgrade")

    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print("[Dataspace] pip error:", res.stderr)
        raise RuntimeError(res.stderr)

    if str(libs) not in sys.path:
        sys.path.insert(0, str(libs))
    importlib.invalidate_caches()


# --- Try importing dataspace_client ---
try:
    from dataspace_client import DataHub
except Exception:
    try:
        print("[Dataspace] dataspace_client saknas – installerar...")
        _install_dataspace_client(upgrade=True)
        from dataspace_client import DataHub
        print("[Dataspace] dataspace_client installerad.")
    except Exception as e:
        raise RuntimeError(
            f"dataspace_client kunde inte installeras automatiskt. "
            f"Installera manuellt i Blenders Python. Fel: {e}"
        )

# --- Initialize DataHub ---
datahub = DataHub()
_KNOWN_SERVERS = set()

# --- URL and credential helpers ---
def _server_base_from_url(url: str) -> str:
    if not url:
        return ""
    s = url.strip()
    if s.startswith("mqtt://"):
        rest = s[len("mqtt://"):]
        host = rest.split('/', 1)[0]
        return f"mqtt://{host}"
    if "://" not in s:
        return f"mqtt://{s.split('/', 1)[0]}"
    return s.split('/', 1)[0]


def _split_folder_and_name_from_url(url: str):
    if not url:
        return "", ""
    if url.endswith('/'):
        return url, ""
    base = os.path.basename(url)
    folder = url[: len(url) - len(base)]
    if not folder.endswith('/'):
        folder += '/'
    return folder, base


def _join_mqtt_path(folder: str, name: str) -> str:
    if not folder.endswith("/"):
        folder += "/"
    return folder + name


def _parent_folder(path: str) -> str:
    p = path.strip()
    if not p.endswith('/'):
        p += '/'
    if p.startswith('mqtt://'):
        rest = p[len('mqtt://'):]
        parts = rest.split('/')
        host = parts[0]
        segs = [s for s in parts[1:] if s]
        if segs:
            segs = segs[:-1]
        new_tail = '/'.join(segs)
        return f"mqtt://{host}/" + (new_tail + '/' if new_tail else '')
    parts = p.strip('/').split('/')
    if len(parts) > 1:
        return '/'.join(parts[:-1]) + '/'
    return '/'


def _ensure_credentials_for_url(url: str) -> bool:
    base = _server_base_from_url(url)
    if not base:
        return True
    if base in _KNOWN_SERVERS:
        return True
    try:
        bpy.ops.datahub.add_credentials('INVOKE_DEFAULT', server=base)
    except Exception:
        pass
    return False


def _list_folder_entries(folder_path: str):
    """Return (display_name, full_mqtt_path) for entries in a dataspace folder."""
    if not folder_path.endswith("/"):
        folder_path += "/"
    listing = datahub.Get(folder_path, handler=None)

    if isinstance(listing, (str, bytes, bytearray)):
        try:
            if isinstance(listing, (bytes, bytearray)):
                listing = listing.decode("utf-8", errors="replace")
            listing = json.loads(listing)
        except Exception as e:
            raise TypeError(f"Expected list from DataHub.Get, got text not JSON: {e}")

    if not isinstance(listing, (list, tuple)):
        raise TypeError(f"DataHub.Get('{folder_path}') expected list/tuple, got {type(listing)!r}")

    items = []
    for name in listing:
        if not isinstance(name, str):
            continue
        is_dir = name.endswith('/')
        base = name[:-1] if is_dir else name
        full_path = folder_path + base + ('/' if is_dir else '')
        disp = (os.path.basename(base) or base) + ('/' if is_dir else '')
        if is_dir or base.lower().endswith('.glb'):
            items.append((disp, full_path))
    return items
