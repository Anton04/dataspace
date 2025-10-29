import bpy
import os
import tempfile
import urllib.request
import fnmatch  # --- ÄNDRING --- nytt import för mönstermatchning

addon_keymaps = []

# ------------------------------------------------------------
#  HJÄLPSFUNKTIONER
# ------------------------------------------------------------

# --- ÄNDRING ---
# Global tabell för registrerade handlers
registered_handlers = []

def register_handler(patterns, handler_func):
    """Registrera en handler för en lista av mönster"""
    global registered_handlers
    for pattern in patterns:
        registered_handlers.append((pattern, handler_func))
    print(f"[SmartPaste] Registrerade handler för: {patterns}")

def find_handler_for_clip(clip: str):
    """Returnera första matchande handler baserat på registrerade mönster"""
    for pattern, func in registered_handlers:
        if fnmatch.fnmatch(clip, pattern):
            return func
    return None  # ingen match → default används

# --- Ursprungliga hjälpfunktioner ---
def handle_mqtt_url(url: str):
    """Körs när text börjar med mqtt:// eller mqtts://"""
    print(f"[SmartPaste] MQTT-URL upptäckt: {url}")
    # Här kan du anropa din riktiga hantering senare
    # Ex: bpy.ops.dataspace.import_url(url=url)


def import_glb_from_url(url: str):
    """Ladda ned och importera en .glb-fil från nätet"""
    print(f"[SmartPaste] GLB-URL upptäckt: {url}")
    try:
        tmpdir = tempfile.gettempdir()
        filename = os.path.join(tmpdir, os.path.basename(url))
        print(f"[SmartPaste] Hämtar {url} → {filename}")
        urllib.request.urlretrieve(url, filename)
        bpy.ops.import_scene.gltf(filepath=filename)
        print(f"[SmartPaste] Import klar: {filename}")
    except Exception as e:
        print(f"[SmartPaste] Fel vid GLB-import: {e!r}")

# ------------------------------------------------------------
#  OPERATORER
# ------------------------------------------------------------

PRESENT_IN_INTERNAL = ""

class VIEW3D_OT_smart_copy(bpy.types.Operator):
    """Töm systemclipboard innan vanlig kopiering i 3D-vyn"""
    bl_idname = "view3d.smart_copy"
    bl_label = "Smart Copy"

    def execute(self, context):
        global PRESENT_IN_INTERNAL
        wm = context.window_manager
        wm.clipboard = ""
        PRESENT_IN_INTERNAL = ""
        print("[SmartCopy] Clipboard rensad – kör copybuffer().")
        
        sel = context.selected_objects
        print(f"[SmartCopy] Antal valda objekt i 3D vyn: {len(sel)}")
        
        try:
            bpy.ops.view3d.copybuffer()
            print("[SmartCopy] Objekt kopierat till intern buffer.")

            # Check if only one are selected and if it is a dataspace object
            

            if len(sel) > 0:
                obj = sel[0]

                # Kontrollera om objektet har dataspace-url
                url = obj.get("datahub_url", None)

                if url:
                    # Kopiera till externa clipboarden
                    wm.clipboard = url
                    print(f"[SmartCopy] Objekt har datahub_url → Kopierat '{url}' till systemclipboard.")
                    PRESENT_IN_INTERNAL = url

                
        except Exception as e:
            print(f"[SmartCopy] Fel vid copybuffer(): {e!r}")
        return {'FINISHED'}
    



class VIEW3D_OT_smart_paste(bpy.types.Operator):
    """Klistrar in objekt, text eller hanterar URLer beroende på clipboard"""
    bl_idname = "view3d.smart_paste"
    bl_label = "Smart Paste"

    def execute(self, context):
        wm = context.window_manager
        clip = (wm.clipboard or "").strip()

        if not clip :
            print("[SmartPaste] Clipboard tomt → försöker klistra in objekt.")
            try:
                bpy.ops.view3d.pastebuffer()
                print("[SmartPaste] Objekt inklistrat.")
            except Exception as e:
                print(f"[SmartPaste] Fel vid pastebuffer(): {e!r}")
            return {'FINISHED'}
        
        if clip == PRESENT_IN_INTERNAL:
            print("[SmartPaste] Clipboard matchar intern buffer → klistrar in objekt.")
            try:
                bpy.ops.view3d.pastebuffer()
                print("[SmartPaste] Objekt inklistrat från intern buffer.")
            except Exception as e:
                print(f"[SmartPaste] Fel vid pastebuffer(): {e!r}")
            return {'FINISHED'}

        # --- ÄNDRING ---
        # 1. Kolla först om någon handler är registrerad som matchar
        matched_handler = find_handler_for_clip(clip)
        if matched_handler:
            print(f"[SmartPaste] Handler funnen för {clip} → {matched_handler.__name__}")
            try:
                matched_handler(clip)
            except Exception as e:
                print(f"[SmartPaste] Fel i handler {matched_handler.__name__}: {e!r}")
            #wm.clipboard = ""
            return {'FINISHED'}
        # --- SLUT ÄNDRING ---

        # Annan text → skapa 3D-text (default handler)
        print(f"[SmartPaste] Ingen match → skapa 3D-text: {clip!r}")
        bpy.ops.object.text_add(location=(0, 0, 0))
        obj = context.object
        obj.data.body = clip
        obj.name = "ClipboardText"
        obj.data.align_x = 'CENTER'
        obj.data.align_y = 'CENTER'
        wm.clipboard = ""
        print(f"[SmartPaste] Skapade 3D-textobjekt: {obj.name}")
        return {'FINISHED'}

# ------------------------------------------------------------
#  REGISTRERING
# ------------------------------------------------------------

def register():

    try:
        unregister()
    except Exception:
        pass


    bpy.utils.register_class(VIEW3D_OT_smart_copy)
    bpy.utils.register_class(VIEW3D_OT_smart_paste)

    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')

    kmi_copy = km.keymap_items.new(VIEW3D_OT_smart_copy.bl_idname, type='C', value='PRESS', ctrl=True)
    kmi_copy_osx = km.keymap_items.new(VIEW3D_OT_smart_copy.bl_idname, type='C', value='PRESS', oskey=True)

    kmi_paste = km.keymap_items.new(VIEW3D_OT_smart_paste.bl_idname, type='V', value='PRESS', ctrl=True)
    kmi_paste_osx = km.keymap_items.new(VIEW3D_OT_smart_paste.bl_idname, type='V', value='PRESS', oskey=True)

    addon_keymaps.extend([kmi_copy, kmi_copy_osx, kmi_paste, kmi_paste_osx])
    print("[INFO] Smart Copy/Paste-URL aktiv.")

    # --- ÄNDRING ---
    # Registrera standardhandlers vid register()
    #register_handler(["mqtt://*", "mqtts://*"], handle_mqtt_url)
    register_handler(["https://*.glb"], import_glb_from_url)
    # --- SLUT ÄNDRING ---


def unregister():
    for km in addon_keymaps:
        try:
            bpy.context.window_manager.keyconfigs.addon.keymaps['3D View'].keymap_items.remove(km)
        except Exception:
            pass
    addon_keymaps.clear()
    bpy.utils.unregister_class(VIEW3D_OT_smart_copy)
    bpy.utils.unregister_class(VIEW3D_OT_smart_paste)
    # --- ÄNDRING ---
    registered_handlers.clear()
    # --- SLUT ÄNDRING ---


if __name__ == "__main__":
    register()
