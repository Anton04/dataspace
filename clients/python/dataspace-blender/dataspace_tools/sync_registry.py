# sync_registry.py
import time
import bpy
from . import helpers

_SYNC_REGISTRY = {}

def register_sync(obj: bpy.types.Object, url: str, status: str = "synced"):
    """Register a new object under the given URL."""
    if not url:
        return
    entry = {
        "synced": time.time(),
        "status": status,
        "root": obj
    }
    _SYNC_REGISTRY.setdefault(url, []).append(entry)
    print(f"[Sync] Registered {obj.name} for {url} ({status})")


def get_entries(url: str):
    """Return all sync entries for a given URL."""
    return _SYNC_REGISTRY.get(url, [])


def update_status(url: str, obj: bpy.types.Object, new_status: str):
    """Update status for a given object+URL pair."""
    for entry in _SYNC_REGISTRY.get(url, []):
        if entry["root"] == obj:
            entry["status"] = new_status
            entry["synced"] = time.time()
            break


def remove_entry(url: str, obj: bpy.types.Object):
    """Remove an entry when an object is deleted or unlinked."""
    if url not in _SYNC_REGISTRY:
        return
    _SYNC_REGISTRY[url] = [e for e in _SYNC_REGISTRY[url] if e["root"] != obj]
    if not _SYNC_REGISTRY[url]:
        del _SYNC_REGISTRY[url]


def diff_against_remote(url: str, remote_objs: list[bpy.types.Object]):
    """Compare imported remote objects with local registry and detect differences.

    Returns:
        dict with keys: {"unchanged": [...], "to_replace": [...], "conflicts": [...]}
    """
    results = {"unchanged": [], "to_replace": [], "conflicts": []}
    local_entries = _SYNC_REGISTRY.get(url, [])
    remote_hashes = {helpers.mesh_signature(o): o for o in remote_objs if helpers.mesh_signature(o)}

    for entry in local_entries:
        obj = entry["root"]
        local_hash = helpers.mesh_signature(obj)
        if not local_hash:
            continue

        # case 1: hash match → unchanged
        if local_hash in remote_hashes:
            results["unchanged"].append(obj)
            continue

        # case 2: hash differs — see if user modified since last sync
        if helpers.is_modified_since_import(obj):
            results["conflicts"].append(obj)
            entry["status"] = "conflict"
        else:
            results["to_replace"].append(obj)
            entry["status"] = "outdated"

    # mark newly synced remote objs
    for o in remote_objs:
        register_sync(o, url, status="synced")

    return results
def print_registry():
    """Print the current sync registry for debugging."""
    print("[Sync Registry]")
    for url, entries in _SYNC_REGISTRY.items():
        print(f"  URL: {url}")
        for entry in entries:
            obj = entry["root"]
            status = entry["status"]
            synced_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["synced"]))
            print(f"    Object: {obj.name}, Status: {status}, Synced: {synced_time}")

            