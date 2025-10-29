# helpers.py
import bpy
import hashlib
from typing import Optional, Iterable
import time

DATAHUB_URL_PROP = "datahub_url"

# ============================================================
#  TRANSFORM-BASED TRACKING (loc/rot/scale changes)
# ============================================================

def mark_imported(obj: bpy.types.Object) -> None:
    """Mark an object as imported by storing its transform (loc/rot/scale)."""
    try:
        obj["_import_loc"]   = tuple(obj.location)
        obj["_import_rot"]   = tuple(obj.rotation_euler)
        obj["_import_scale"] = tuple(obj.scale)
        obj["_imported"]     = True
    except Exception:
        # Avoid crashing on non-standard objects
        pass


def is_transform_modified(obj: bpy.types.Object) -> bool:
    """Return True if transform changed since import; False if unchanged or not tracked."""
    if not obj.get("_imported"):
        return False  # not tracked → treat as unchanged (adjust if you prefer True)
    try:
        if tuple(obj.location) != tuple(obj["_import_loc"]):        return True
        if tuple(obj.rotation_euler) != tuple(obj["_import_rot"]):  return True
        if tuple(obj.scale) != tuple(obj["_import_scale"]):         return True
    except Exception:
        # Missing markers ⇒ assume modified
        return True
    return False


# ============================================================
#  MESH-HASH-BASED TRACKING (geometry changes)
# ============================================================

def mesh_signature(obj: bpy.types.Object) -> Optional[str]:
    """Return a stable MD5 hash of mesh vertex data, or None for non-mesh."""
    me = getattr(obj, "data", None)
    if not me or me.__class__.__name__ != "Mesh":
        return None

    # Hash vertex coordinates; extend with edges/polygons if stricter checks are needed
    md5 = hashlib.md5()
    for v in me.vertices:
        # v.co is a Vector; slice coerces to tuple of floats
        md5.update(v.co[:])
    return md5.hexdigest()


def mark_imported_mesh(obj: bpy.types.Object) -> None:
    """Store the current mesh signature to allow later change detection."""
    sig = mesh_signature(obj)
    if sig:
        obj["_import_meshsig"] = sig
        obj["_imported_mesh"] = True


def mesh_modified_since_import(obj: bpy.types.Object) -> bool:
    """Return True if current mesh signature differs from stored import signature."""
    if not obj.get("_imported_mesh"):
        return False
    sig_now = mesh_signature(obj)
    sig_old = obj.get("_import_meshsig")
    if not sig_now or not sig_old:
        return False
    return sig_now != sig_old


# ============================================================
#  COMBINED CHECK
# ============================================================

def is_modified_since_import(obj: bpy.types.Object) -> bool:
    """Return True if either transform OR mesh changed since import."""
    return is_transform_modified(obj) or mesh_modified_since_import(obj)


# ============================================================
#  METADATA HELPERS (IMPORT / PUBLISH)
# ============================================================

def set_import_metadata(obj: bpy.types.Object, url: str = "", with_mesh_hash: bool = True) -> None:
    """Set datahub URL and mark object as imported (transform + optional mesh hash)."""

    

    try:
        print(f"[Dataspace] Setting import metadata on object '{obj.name}' with URL: {url}")
        obj[DATAHUB_URL_PROP] = url
    except Exception:
        print(f"[Dataspace] Warning: could not set datahub_url on object '{obj.name}'")

    try:
        obj["sync_time"] = time.time()
    except Exception:
        pass

    mark_imported(obj)
    if with_mesh_hash:
        mark_imported_mesh(obj)


# ============================================================
#  RECURSIVE MARKING
# ============================================================

def mark_imported_recursive(root: bpy.types.Object, include_children: bool = True, use_mesh_sig: bool = True) -> None:
    """Mark one or many objects as imported; optionally include children and mesh hash."""
    stack = [root]
    while stack:
        o = stack.pop()
        mark_imported(o)
        if use_mesh_sig:
            mark_imported_mesh(o)
        if include_children:
            stack.extend(list(o.children))


def set_published_metadata_recursive(objs: Iterable[bpy.types.Object], target_url: str, refresh_hash: bool = True) -> None:
    """After publish: set new datahub URL and refresh import markers so the
    objects are considered 'clean' (not modified) right after export."""
    for o in objs:
        set_import_metadata(o, url=target_url, with_mesh_hash=refresh_hash)
