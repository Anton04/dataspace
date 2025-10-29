bl_info = {
    "name": "Dataspace GLB Tools",
    "author": "Anton + ChatGPT",
    "version": (0, 6, 3),  # UI rename to Dataspace; set datahub_url on publish; quick publish; creds dialog kept
    "blender": (4, 5, 0),
    "location": "3D Viewport > N-panel > Dataspace; File > Import/Export",
    "description": "Browse Dataspace folders, import remote GLB, and publish selected objects as GLB",
    "category": "Import-Export",
}

import bpy
import time
import os
import tempfile
import addon_utils
from typing import List, Tuple, Iterable

# --- DEPENDENCY BUTTON (short + self-contained) ------------------------------
import os, sys
import bpy

ADDON_DIR = os.path.dirname(__file__)
MODULES_DIR = os.path.join(ADDON_DIR, "modules")
if os.path.isdir(MODULES_DIR) and MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)


class DATASPACETOOLS_Preferences(bpy.types.AddonPreferences):
    bl_idname = __name__  # eller "dataspace_tools" om ditt paketnamn är fixerat

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Beroenden")
        col.operator("dataspace_tools.install_deps", icon="CONSOLE")


class DATASPACETOOLS_OT_InstallDeps(bpy.types.Operator):
    bl_idname = "dataspace_tools.install_deps"
    bl_label = "Installera beroenden"
    bl_description = "Installerar Python-paket i add-onens lokala 'modules'"

    def execute(self, context):
        try:
            from .deps import ensure_deps
        except Exception as e:
            self.report({'ERROR'}, f"Kunde inte importera deps: {e}")
            return {'CANCELLED'}

        ok, msg = ensure_deps(
            target_dir=MODULES_DIR,
            requirements=[
                # Lägg dina paket här, pinna gärna versioner
                "dataspace_client",  # ex.
                # "paho-mqtt==2.1.0",
            ],
        )
        self.report({'INFO' if ok else 'ERROR'}, msg)
        return {'FINISHED'}

# Registrera klasserna
_classes_deps = (
    DATASPACETOOLS_Preferences,
    DATASPACETOOLS_OT_InstallDeps,
)


# --- Bootstrap: importera DataHub, annars installera dataspace_client och försök igen ---
import sys, os, subprocess, importlib, pathlib

_ADDON_DIR = pathlib.Path(__file__).parent
_LIBS_DIR = _ADDON_DIR / "libs"
os.makedirs(_LIBS_DIR, exist_ok=True)
if str(_LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(_LIBS_DIR))

def _install_dataspace_client(upgrade: bool = True) -> None:
    """Installera dataspace_client till add-onets /libs med Blenders Python."""
    py = sys.executable
    # Se till att pip finns
    try:
        subprocess.check_call([py, "-m", "ensurepip", "--upgrade"])
    except Exception:
        pass  # ok om ensurepip redan finns/inte behövs
    # Bygg pip-kommandot
    cmd = [py, "-m", "pip", "install", "dataspace_client", "-t", str(_LIBS_DIR)]
    if upgrade:
        cmd.insert(4, "--upgrade")  # -> pip install --upgrade dataspace_client -t libs
    # Kör installationen
    subprocess.check_call(cmd)
    # Ladda om importcacher
    importlib.invalidate_caches()

# Försök importera; installera vid behov; försök igen.
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


# ---- Dataspace (library object is still named DataHub) ----
try:
    from dataspace_client import DataHub
except Exception as e:
    raise RuntimeError("dataspace_client is not installed in Blender's Python. Install it in Blender's Python.") from e

# Init DataHub (no default credentials)
datahub = DataHub()

# Known servers we've added credentials for (session-local)
_KNOWN_SERVERS = set()

# -----------------
# Addon / GLTF I/O
# -----------------

def _ensure_gltf_addons():
    """Make sure glTF importer/exporter are enabled."""
    for mod in ("io_scene_gltf2",):
        try:
            addon_utils.enable(mod, default_set=True, persistent=True)
        except Exception:
            pass


def import_glb_bytes(data: bytes, select_import: bool = True, frame_view: bool = True) -> List[bpy.types.Object]:
    """Import GLB binary bytes into the current scene and return created objects."""
    _ensure_gltf_addons()

    # Write to a temporary file (glTF importer expects a path)
    fd, glb_path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    with open(glb_path, "wb") as f:
        f.write(data)

    # Capture pre-import objects
    prev = set(bpy.data.objects)

    # Import (works for .glb as well)
    bpy.ops.import_scene.gltf(filepath=glb_path)

    # New objects
    new_objs = [o for o in bpy.data.objects if o not in prev]

    # Optional selection + frame
    if select_import and new_objs:
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in new_objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = new_objs[0]
        if frame_view:
            try:
                bpy.ops.view3d.view_selected(use_all_regions=False)
            except Exception:
                pass

    # Cleanup temp
    try:
        os.remove(glb_path)
    except Exception:
        pass

    return new_objs


def _export_selected_to_glb_bytes(apply_modifiers: bool = True) -> Tuple[bytes, List[bpy.types.Object]]:
    """Export selected objects to a temporary GLB file and return (bytes, exported_objects)."""
    sel = [o for o in bpy.context.view_layer.objects if o.select_get() and o.type in {"MESH", "EMPTY", "ARMATURE", "CURVE", "SURFACE", "META", "FONT", "VOLUME"}]
    if not sel:
        raise RuntimeError("No selectable objects chosen. Select objects to export.")

    _ensure_gltf_addons()

    fd, tmp_path = tempfile.mkstemp(suffix=".glb")
    os.close(fd)

    # Ensure only intended objects are exported
    prev_selection = [o for o in bpy.context.selected_objects]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in sel:
        o.select_set(True)
    bpy.context.view_layer.objects.active = sel[0]

    try:
        res = bpy.ops.export_scene.gltf(
            filepath=tmp_path,
            export_format='GLB',
            use_selection=True,
            export_apply=apply_modifiers,
        )
        if res != {'FINISHED'}:
            raise RuntimeError("GLB export did not finish successfully")
        with open(tmp_path, 'rb') as f:
            payload = f.read()
    finally:
        # Restore selection
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in prev_selection:
            o.select_set(True)
        if prev_selection:
            bpy.context.view_layer.objects.active = prev_selection[0]
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return payload, list(sel)


# ---------------------------------
# URL/Path helpers & credentials
# ---------------------------------

def _server_base_from_url(url: str) -> str:
    """Return scheme://host part of an mqtt URL (e.g. mqtt://iot.digivis.se)."""
    if not url:
        return ""
    s = url.strip()
    if s.startswith("mqtt://"):
        rest = s[len("mqtt://"):]
        host = rest.split('/', 1)[0]
        return f"mqtt://{host}"
    # Fallback: if user typed just host
    if "://" not in s:
        return f"mqtt://{s.split('/',1)[0]}"
    return s.split('/', 1)[0]


def _split_folder_and_name_from_url(url: str) -> Tuple[str, str]:
    """Split an mqtt://... path into (folder_with_trailing_slash, filename). If url ends with '/', returns (url, "")."""
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
    """Return the parent directory of an mqtt:// path, keeping scheme+host intact."""
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
        newp = f"mqtt://{host}/" + (new_tail + '/' if new_tail else '')
        return newp
    # generic fallback
    parts = p.strip('/').split('/')
    if len(parts) > 1:
        return '/'.join(parts[:-1]) + '/'
    return '/'


def _ensure_credentials_for_url(url: str) -> bool:
    """If server hasn't been added yet, prompt user to add credentials.
    Returns True if credentials are (assumed) present; False if we just opened a dialog.
    NOTE: This may open behind another dialog in some Blender versions; users can use the ➕ button to add creds explicitly.
    """
    base = _server_base_from_url(url)
    if not base:
        return True
    if base in _KNOWN_SERVERS:
        return True
    # Prompt user to add creds (prefill server)
    try:
        bpy.ops.datahub.add_credentials('INVOKE_DEFAULT', server=base)
    except Exception:
        pass
    return False


# ---------------------------------
# Listing with JSON parsing support
# ---------------------------------

def _list_folder_entries(folder_path: str) -> List[Tuple[str, str]]:
    """Return (display_name, full_mqtt_path) for entries in a dataspace folder.

    Assumes DataHub.Get returns a list of strings (names). If str/bytes are returned,
    a minimal json.loads is attempted to convert to a Python list.

    Behaviour:
      • Folders keep trailing '/' in display and path, files don't.
      • Only .glb files are returned among files (folders are always returned).
      • Full MQTT paths are constructed by joining names with folder_path.
    """
    import json

    if not folder_path.endswith("/"):
        folder_path = folder_path + "/"

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

    items: List[Tuple[str, str]] = []
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


# -----------------------
# UI List & data models
# -----------------------

class DataHubListItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    path: bpy.props.StringProperty(name="Path")
    is_dir: bpy.props.BoolProperty(name="Is Dir", default=False)


class DATAHUB_UL_entries(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_id = 'FILE_FOLDER' if item.is_dir else 'FILE'
        layout.label(text=item.name, icon=icon_id)


# -----------------------
# State container (path) + active ops
# -----------------------
class _DHState:
    folder_path: str = "mqtt://iot.digivis.se/datadirectory/TestArea/TestFiles/"

_ACTIVE_IMPORT_OP = None
_ACTIVE_PUBLISH_OP = None

# Store URL on imported objects
DATAHUB_URL_PROP = "datahub_url"

# -----------------------
# Mouse-click debug + double-click action (via WindowManager index)
# -----------------------

DEBUG_CLICKS = True
DOUBLE_CLICK_S = 0.35  # seconds

def _active_dialog():
    global _ACTIVE_PUBLISH_OP, _ACTIVE_IMPORT_OP
    if isinstance(_ACTIVE_PUBLISH_OP, DATAHUB_OT_publish_browse_glb):
        return _ACTIVE_PUBLISH_OP
    if isinstance(_ACTIVE_IMPORT_OP, DATAHUB_OT_import_remote_glb):
        return _ACTIVE_IMPORT_OP
    return None


def datahub_on_entry_click(wm, context):
    from time import monotonic
    op = _active_dialog()
    if op is None:
        return

    if getattr(op, "_suppress_clicks", 0) > 0:
        op._suppress_clicks -= 1
        op._last_click_idx = -1
        op._last_click_time = 0.0
        return

    idx = context.window_manager.datahub_entry_index
    now = monotonic()

    prev_idx = getattr(op, "_last_click_idx", -1)
    prev_t   = getattr(op, "_last_click_time", 0.0)
    dt = now - prev_t
    is_double = (idx == prev_idx) and (dt <= DOUBLE_CLICK_S)

    name = path = ""
    is_dir = False
    if 0 <= idx < len(op.entries):
        it = op.entries[idx]
        name, path, is_dir = it.name, it.path, it.is_dir

    if DEBUG_CLICKS:
        kind = "DOUBLE" if is_double else "SINGLE"
        print(f"[Dataspace][{kind}] idx={idx} dt={dt:.3f}s name='{name}' is_dir={is_dir} path='{path}'")
        try:
            op.report({'INFO'}, f"{kind} click: {name or '(none)'}")
        except Exception:
            pass

    if isinstance(op, DATAHUB_OT_publish_browse_glb) and 0 <= idx < len(op.entries) and not is_dir:
        base = os.path.basename(path.rstrip('/'))
        if not base.lower().endswith('.glb'):
            base += '.glb'
        op.file_name = base

    if is_double and 0 <= idx < len(op.entries):
        op._last_click_idx = -1
        op._last_click_time = 0.0

        if isinstance(op, DATAHUB_OT_import_remote_glb):
            try:
                op._suppress_clicks = 1
                bpy.ops.datahub.open_or_import()
            except Exception as e:
                print("[Dataspace][DOUBLE] import action error:", e)
        elif isinstance(op, DATAHUB_OT_publish_browse_glb):
            if is_dir:
                op._suppress_clicks = 1
                op.folder_path = path if path.endswith('/') else path + '/'
                op._refresh_entries()
                try:
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
                except Exception:
                    pass
            else:
                try:
                    bpy.ops.datahub.publish_now('INVOKE_DEFAULT')
                except Exception as e:
                    print("[Dataspace][DOUBLE] publish action error:", e)
    else:
        op._last_click_idx = idx
        op._last_click_time = now


# -----------------------
# Utility operators
# -----------------------

class DATAHUB_OT_add_credentials(bpy.types.Operator):
    bl_idname = "datahub.add_credentials"
    bl_label = "Dataspace: Add Credentials"
    bl_options = {'REGISTER', 'INTERNAL'}

    server: bpy.props.StringProperty(name="Server", description="e.g. mqtt://iot.digivis.se", default="")
    username: bpy.props.StringProperty(name="Username", default="")
    password: bpy.props.StringProperty(name="Password", default="", subtype='PASSWORD')

    def invoke(self, context, event):
        if not self.server:
            op = _active_dialog()
            if op:
                self.server = _server_base_from_url(getattr(op, 'folder_path', ''))
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        base = _server_base_from_url(self.server)
        if not base:
            self.report({'ERROR'}, "Invalid server")
            return {'CANCELLED'}
        try:
            datahub.add_credentials(base, self.username, self.password)
            _KNOWN_SERVERS.add(base)
            op = _active_dialog()
            if op:
                try:
                    op._refresh_entries()
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
                except Exception:
                    pass
            self.report({'INFO'}, f"Credentials added for {base}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add credentials: {e}")
            return {'CANCELLED'}


class DATAHUB_OT_refresh_listing(bpy.types.Operator):
    bl_idname = "datahub.refresh_listing"
    bl_label = "Dataspace: Refresh Listing"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        op = _active_dialog()
        if not op:
            self.report({'WARNING'}, "Open the dialog to refresh.")
            return {'CANCELLED'}
        op._refresh_entries()
        try:
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
        except Exception:
            pass
        self.report({'INFO'}, "Listing refreshed")
        return {'FINISHED'}


class DATAHUB_OT_go_up_folder(bpy.types.Operator):
    bl_idname = "datahub.go_up_folder"
    bl_label = "Dataspace: Go Up"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        op = _active_dialog()
        if not op:
            self.report({'WARNING'}, "Open the dialog to navigate.")
            return {'CANCELLED'}
        op._suppress_clicks = max(getattr(op, "_suppress_clicks", 0), 1)
        op.folder_path = _parent_folder(op.folder_path)
        op._refresh_entries()
        try:
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
        except Exception:
            pass
        self.report({'INFO'}, f"Now in: {op.folder_path}")
        return {'FINISHED'}


class DATAHUB_OT_open_selected(bpy.types.Operator):
    bl_idname = "datahub.open_selected"
    bl_label = "Dataspace: Open Folder"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        op = _active_dialog()
        if not op:
            self.report({'WARNING'}, "Open the dialog to navigate.")
            return {'CANCELLED'}
        wm = bpy.context.window_manager
        idx = wm.datahub_entry_index
        if idx < 0 or idx >= len(op.entries):
            self.report({'WARNING'}, "No item selected")
            return {'CANCELLED'}
        item = op.entries[idx]
        if not item.is_dir:
            self.report({'WARNING'}, "Selected item is not a folder")
            return {'CANCELLED'}
        op._suppress_clicks = max(getattr(op, "_suppress_clicks", 0), 1)
        op.folder_path = item.path if item.path.endswith('/') else item.path + '/'
        op._refresh_entries()
        try:
            bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
        except Exception:
            pass
        return {'FINISHED'}


class DATAHUB_OT_import_selected(bpy.types.Operator):
    bl_idname = "datahub.import_selected"
    bl_label = "Dataspace: Import File"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        op = _ACTIVE_IMPORT_OP
        if not isinstance(op, DATAHUB_OT_import_remote_glb):
            self.report({'WARNING'}, "Open the import dialog to import.")
            return {'CANCELLED'}
        wm = bpy.context.window_manager
        idx = wm.datahub_entry_index
        if idx < 0 or idx >= len(op.entries):
            self.report({'WARNING'}, "No item selected")
            return {'CANCELLED'}
        item = op.entries[idx]
        if item.is_dir:
            self.report({'WARNING'}, "Selected item is a folder. Use Open.")
            return {'CANCELLED'}
        try:
            if not _ensure_credentials_for_url(item.path):
                self.report({'INFO'}, "Add credentials and refresh.")
                return {'CANCELLED'}
            data = datahub.Get(item.path, handler=None)
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError("DataHub.Get did not return bytes for a file path")
            new_objs = import_glb_bytes(data, op.select_import, op.frame_view)
            for o in new_objs:
                try:
                    o[DATAHUB_URL_PROP] = item.path
                except Exception:
                    pass
            try:
                bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
            except Exception:
                pass
            self.report({'INFO'}, f"Imported {len(new_objs)} objects from {item.name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}


class DATAHUB_OT_open_or_import(bpy.types.Operator):
    bl_idname = "datahub.open_or_import"
    bl_label = "Dataspace: Open or Import"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        op = _ACTIVE_IMPORT_OP
        if not isinstance(op, DATAHUB_OT_import_remote_glb):
            self.report({'WARNING'}, "Open the import dialog to act.")
            return {'CANCELLED'}
        wm = bpy.context.window_manager
        idx = wm.datahub_entry_index
        if idx < 0 or idx >= len(op.entries):
            self.report({'WARNING'}, "No item selected")
            return {'CANCELLED'}
        item = op.entries[idx]
        if item.is_dir:
            op._suppress_clicks = max(getattr(op, "_suppress_clicks", 0), 1)
            op.folder_path = item.path if item.path.endswith('/') else item.path + '/'
            if not _ensure_credentials_for_url(op.folder_path):
                self.report({'INFO'}, "Add credentials and refresh.")
                return {'CANCELLED'}
            op._refresh_entries()
            try:
                bpy.ops.wm.redraw_timer(type='DRAW_WIN', iterations=1)
            except Exception:
                pass
            return {'FINISHED'}
        try:
            if not _ensure_credentials_for_url(item.path):
                self.report({'INFO'}, "Add credentials and refresh.")
                return {'CANCELLED'}
            data = datahub.Get(item.path, handler=None)
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError("DataHub.Get did not return bytes for a file path")
            new_objs = import_glb_bytes(data, op.select_import, op.frame_view)
            for o in new_objs:
                try:
                    o[DATAHUB_URL_PROP] = item.path
                except Exception:
                    pass
            self.report({'INFO'}, f"Imported {len(new_objs)} objects from {item.name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}


class DATAHUB_OT_publish_now(bpy.types.Operator):
    """Publish selected objects to current folder + file name field.
    If the file already exists, ask for overwrite confirmation showing just the file name.
    After publish, set datahub_url on exported objects to the new target path.
    """
    bl_idname = "datahub.publish_now"
    bl_label = "Dataspace: Publish GLB"
    bl_options = {'REGISTER', 'UNDO'}

    _target_fname = None
    _target_folder = None
    _apply_mods = True

    def _compute_target_name(self, op):
        name = (op.file_name or "").strip() or "untitled.glb"
        if not name.lower().endswith('.glb'):
            name += '.glb'
        return name

    def _name_exists(self, op, fname: str) -> bool:
        target = fname.lower()
        for it in op.entries:
            if not it.is_dir and it.name.lower() == target:
                return True
        return False

    def draw(self, context):
        if self._target_fname:
            col = self.layout.column()
            col.label(text=f"Do you want to overwrite {self._target_fname}?", icon='ERROR')

    def invoke(self, context, event):
        op = _ACTIVE_PUBLISH_OP
        if not isinstance(op, DATAHUB_OT_publish_browse_glb):
            self.report({'WARNING'}, "Open the publish dialog first.")
            return {'CANCELLED'}

        if not _ensure_credentials_for_url(op.folder_path):
            self.report({'INFO'}, "Add credentials and try again.")
            return {'CANCELLED'}

        fname = self._compute_target_name(op)
        self._target_fname = fname
        self._target_folder = op.folder_path
        self._apply_mods = op.apply_modifiers

        if self._name_exists(op, fname):
            return context.window_manager.invoke_props_dialog(self, width=420)
        return self.execute(context)

    def execute(self, context):
        op = _ACTIVE_PUBLISH_OP
        if not isinstance(op, DATAHUB_OT_publish_browse_glb):
            self.report({'WARNING'}, "Open the publish dialog first.")
            return {'CANCELLED'}
        try:
            fname = self._target_fname or self._compute_target_name(op)
            folder = self._target_folder or op.folder_path
            payload, exported_objs = _export_selected_to_glb_bytes(self._apply_mods)
            target_path = _join_mqtt_path(folder, fname)
            datahub.Publish(target_path, payload)
            # Set source on exported objects
            for o in exported_objs:
                try:
                    o[DATAHUB_URL_PROP] = target_path
                except Exception:
                    pass
            try:
                op._refresh_entries()
            except Exception:
                pass
            self.report({'INFO'}, f"Published {fname} to {folder}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Publish failed: {e}")
            return {'CANCELLED'}


# -----------------------
# QUICK PUBLISH BACK TO SOURCE (no dialog)
# -----------------------

class DATAHUB_OT_publish_back_now(bpy.types.Operator):
    """Publish the ACTIVE object's geometry back to its stored datahub_url without any dialog.
    Overwrites the source file. Requires the active (or any selected) object to have 'datahub_url'.
    Also refreshes that property to the target after publish.
    """
    bl_idname = "datahub.publish_back_now"
    bl_label = "Dataspace: Quick Publish Back to Source"
    bl_options = {'REGISTER', 'UNDO'}

    apply_modifiers: bpy.props.BoolProperty(name="Apply Modifiers", default=True)

    def _find_source_url(self, context) -> Tuple[bpy.types.Object, str]:
        ctx = context
        act = ctx.view_layer.objects.active
        if act and DATAHUB_URL_PROP in act.keys():
            return act, str(act.get(DATAHUB_URL_PROP))
        for o in ctx.selected_objects:
            if DATAHUB_URL_PROP in o.keys():
                return o, str(o.get(DATAHUB_URL_PROP))
        return None, ""

    def execute(self, context):
        obj, url = self._find_source_url(context)
        if not obj or not url:
            self.report({'ERROR'}, "Active/selected object has no datahub_url")
            return {'CANCELLED'}
        folder, fname = _split_folder_and_name_from_url(url)
        if not folder or not fname:
            self.report({'ERROR'}, "Stored URL is not a file path")
            return {'CANCELLED'}
        if not fname.lower().endswith('.glb'):
            fname += '.glb'

        if not _ensure_credentials_for_url(folder):
            self.report({'INFO'}, "Add credentials and retry quick publish.")
            return {'CANCELLED'}

        ctx = context
        prev_sel = list(ctx.selected_objects)
        prev_active = ctx.view_layer.objects.active

        try:
            for o in prev_sel:
                o.select_set(False)
            obj.select_set(True)
            ctx.view_layer.objects.active = obj

            payload, _ = _export_selected_to_glb_bytes(self.apply_modifiers)
            target_path = _join_mqtt_path(folder, fname)
            datahub.Publish(target_path, payload)
            try:
                obj[DATAHUB_URL_PROP] = target_path
            except Exception:
                pass
            self.report({'INFO'}, f"Quick published to {fname}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Quick publish failed: {e}")
            return {'CANCELLED'}
        finally:
            try:
                for o in ctx.selected_objects:
                    o.select_set(False)
                for o in prev_sel:
                    o.select_set(True)
                if prev_active:
                    ctx.view_layer.objects.active = prev_active
            except Exception:
                pass


# -----------------------
# Import Dialog Operator
# -----------------------

class DATAHUB_OT_import_remote_glb(bpy.types.Operator):
    """Browse a dataspace folder (trailing slash) and import a chosen .glb.
    File-browser-like UI with navigation buttons. Uses OK button as Close.
    """
    bl_idname = "datahub.import_remote_glb"
    bl_label = "Dataspace: Import Remote GLB"
    bl_options = {'REGISTER', 'UNDO'}

    folder_path: bpy.props.StringProperty(
        name="Path",
        description="Dataspace folder path (must end with /)",
        default=_DHState.folder_path,
        update=lambda self, ctx: self._refresh_entries(),
    )
    select_import: bpy.props.BoolProperty(name="Select Imported", default=True)
    frame_view: bpy.props.BoolProperty(name="Frame View", default=True)

    entries: bpy.props.CollectionProperty(type=DataHubListItem)
    entry_index: bpy.props.IntProperty(name="Index", default=-1)

    filter_text: bpy.props.StringProperty(
        name="Search",
        description="Filter by name (folders always shown)",
        default="",
        update=lambda self, ctx: self._refresh_entries(),
    )

    def _refresh_entries(self):
        folder = self.folder_path
        if not folder.endswith('/'):
            folder += '/'
        if not _ensure_credentials_for_url(folder):
            self.entries.clear()
            bpy.context.window_manager.datahub_entry_index = -1
            return
        try:
            items = _list_folder_entries(folder)
        except Exception as e:
            items = []
            print("[Dataspace] list error:", e)
        f = (self.filter_text or "").lower()
        self.entries.clear()
        for disp, fullp in items:
            is_dir = disp.endswith('/')
            name = disp[:-1] if is_dir else disp
            if is_dir or (not f or f in name.lower()):
                it = self.entries.add()
                it.name = disp
                it.path = fullp
                it.is_dir = is_dir
        wm = bpy.context.window_manager
        wm.datahub_entry_index = 0 if len(self.entries) else -1
        _DHState.folder_path = folder

    def invoke(self, context, event):
        global _ACTIVE_IMPORT_OP
        _ACTIVE_IMPORT_OP = self
        self._last_click_idx = -1
        self._last_click_time = 0.0
        self._suppress_clicks = 0

        _ensure_credentials_for_url(self.folder_path)

        self._refresh_entries()
        if bpy.app.version >= (4, 0, 0):
            return context.window_manager.invoke_props_dialog(self, width=900, confirm_text="Close")
        else:
            return context.window_manager.invoke_props_dialog(self, width=900)

    def draw(self, context):
        layout = self.layout
        split = layout.split(factor=0.94, align=True)
        split.prop(self, "folder_path", text="Path")
        r = split.row(align=True)
        r.operator("datahub.go_up_folder", text="", icon='FILE_PARENT')
        r.operator("datahub.refresh_listing", text="", icon='FILE_REFRESH')
        r.operator("datahub.add_credentials", text="", icon='ADD')

        layout.prop(self, "filter_text", text="", icon='VIEWZOOM')

        row = layout.row()
        row.template_list("DATAHUB_UL_entries", "", self, "entries",
                          context.window_manager, "datahub_entry_index", rows=16)

        box = layout.box()
        box.prop(self, "select_import")
        box.prop(self, "frame_view")

        layout.separator()
        footer = layout.column(align=True)
        footer.operator("datahub.open_or_import", text="Open / Import", icon='IMPORT')

    def execute(self, context):
        return {'CANCELLED'}


# -----------------------
# Publish Dialog Operator
# -----------------------

class DATAHUB_OT_publish_browse_glb(bpy.types.Operator):
    """Browse dataspace and publish selected objects as a GLB into chosen folder/filename.
    Same UI/behaviour as the import dialog, with a filename field and Publish action.
    """
    bl_idname = "datahub.publish_browse_glb"
    bl_label = "Dataspace: Publish GLB"
    bl_options = {'REGISTER', 'UNDO'}

    folder_path: bpy.props.StringProperty(
        name="Path",
        description="Dataspace folder path (must end with /)",
        default=_DHState.folder_path,
        update=lambda self, ctx: self._refresh_entries(),
    )
    file_name: bpy.props.StringProperty(
        name="File Name",
        description="Name of the GLB to create",
        default="untitled.glb",
    )
    apply_modifiers: bpy.props.BoolProperty(name="Apply Modifiers", default=True)

    entries: bpy.props.CollectionProperty(type=DataHubListItem)
    entry_index: bpy.props.IntProperty(name="Index", default=-1)

    filter_text: bpy.props.StringProperty(
        name="Search",
        description="Filter by name (folders always shown)",
        default="",
        update=lambda self, ctx: self._refresh_entries(),
    )

    def _prefill_from_selection(self):
        ctx = bpy.context
        url = None
        act = ctx.view_layer.objects.active
        if act and DATAHUB_URL_PROP in act.keys():
            url = act.get(DATAHUB_URL_PROP)
        if not url:
            for o in ctx.selected_objects:
                if DATAHUB_URL_PROP in o.keys():
                    url = o.get(DATAHUB_URL_PROP)
                    break
        if url:
            folder, fname = _split_folder_and_name_from_url(str(url))
            if folder:
                self.folder_path = folder
            if fname:
                if not fname.lower().endswith('.glb'):
                    fname += '.glb'
                self.file_name = fname

    def _refresh_entries(self):
        folder = self.folder_path
        if not folder.endswith('/'):
            folder += '/'
        if not _ensure_credentials_for_url(folder):
            self.entries.clear()
            bpy.context.window_manager.datahub_entry_index = -1
            return
        try:
            items = _list_folder_entries(folder)
        except Exception as e:
            items = []
            print("[Dataspace] list error:", e)
        f = (self.filter_text or "").lower()
        self.entries.clear()
        for disp, fullp in items:
            is_dir = disp.endswith('/')
            name = disp[:-1] if is_dir else disp
            if is_dir or (not f or f in name.lower()):
                it = self.entries.add()
                it.name = disp
                it.path = fullp
                it.is_dir = is_dir
        wm = bpy.context.window_manager
        wm.datahub_entry_index = 0 if len(self.entries) else -1
        _DHState.folder_path = folder

    def invoke(self, context, event):
        global _ACTIVE_PUBLISH_OP
        _ACTIVE_PUBLISH_OP = self
        self._last_click_idx = -1
        self._last_click_time = 0.0
        self._suppress_clicks = 0

        try:
            self._prefill_from_selection()
        except Exception as e:
            print("[Dataspace] prefill error:", e)

        _ensure_credentials_for_url(self.folder_path)

        self._refresh_entries()
        if bpy.app.version >= (4, 0, 0):
            return context.window_manager.invoke_props_dialog(self, width=900, confirm_text="Close")
        else:
            return context.window_manager.invoke_props_dialog(self, width=900)

    def draw(self, context):
        layout = self.layout
        split = layout.split(factor=0.94, align=True)
        split.prop(self, "folder_path", text="Path")
        r = split.row(align=True)
        r.operator("datahub.go_up_folder", text="", icon='FILE_PARENT')
        r.operator("datahub.refresh_listing", text="", icon='FILE_REFRESH')
        r.operator("datahub.add_credentials", text="", icon='ADD')

        layout.prop(self, "filter_text", text="", icon='VIEWZOOM')

        row = layout.row()
        row.template_list("DATAHUB_UL_entries", "", self, "entries",
                          context.window_manager, "datahub_entry_index", rows=16)

        box = layout.box()
        box.prop(self, "file_name", text="File Name")
        box.prop(self, "apply_modifiers")

        layout.separator()
        footer = layout.column(align=True)
        footer.operator("datahub.publish_now", text="Publish", icon='EXPORT')

    def execute(self, context):
        return {'CANCELLED'}


# ---------------
# Menyintegration & Panel
# ---------------

def menu_func_import(self, context):
    self.layout.operator(
        DATAHUB_OT_import_remote_glb.bl_idname,
        text="Dataspace: Import Remote GLB (.glb)"
    )


def menu_func_export(self, context):
    self.layout.operator(
        DATAHUB_OT_publish_browse_glb.bl_idname,
        text="Dataspace: Publish GLB"
    )
    self.layout.operator(
        DATAHUB_OT_publish_back_now.bl_idname,
        text="Dataspace: Quick Publish Back to Source"
    )


class DATAHUB_PT_panel(bpy.types.Panel):
    bl_label = "Dataspace GLB Tools"
    bl_idname = "DATAHUB_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dataspace'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("datahub.import_remote_glb", icon='IMPORT')
        col.operator("datahub.publish_browse_glb", icon='EXPORT')
        col.operator("datahub.publish_back_now", icon='EXPORT')


# ---- Registration ----
classes = (
    DataHubListItem,
    DATAHUB_UL_entries,
    DATAHUB_OT_add_credentials,
    DATAHUB_OT_import_remote_glb,
    DATAHUB_OT_publish_browse_glb,
    DATAHUB_OT_refresh_listing,
    DATAHUB_OT_go_up_folder,
    DATAHUB_OT_open_selected,
    DATAHUB_OT_import_selected,
    DATAHUB_OT_open_or_import,
    DATAHUB_OT_publish_now,
    DATAHUB_OT_publish_back_now,
    DATAHUB_PT_panel,
)

def register():

    for _C in _classes_deps:
        try:
            bpy.utils.register_class(_C)
        except Exception:
            pass
            
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    if not hasattr(bpy.types.WindowManager, "datahub_entry_index"):
        bpy.types.WindowManager.datahub_entry_index = bpy.props.IntProperty(
            name="Dataspace Index", default=-1, update=datahub_on_entry_click
        )


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    except Exception:
        pass

    try:
        del bpy.types.WindowManager.datahub_entry_index
    except Exception:
        pass

    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass

    for _C in reversed(_classes_deps):
        try:
            bpy.utils.unregister_class(_C)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    register()

    test_folder = "mqtt://iot.digivis.se/datadirectory/TestArea/TestFiles/"
    try:
        files = _list_folder_entries(test_folder)
        print("Files and folders:")
        for name, fullp in files:
            print(f" - {name}: {fullp}")
    except Exception as e:
        print("Listing failed:", e)

