import xloil as xlo

import tkinter as tk
from tkinter import ttk, messagebox
import uuid
import hashlib

# Håller listan med tillagda servrar i minnet
_servers = [{"name": "New", "user": "", "pass": ""}]
selected_server = None

storecredentials = True

#Make an excel cell funtion that returns the name of the selected server
@xlo.func
def GetSelectedServerName():
    global selected_server
    if selected_server is None:
        return "None"
    return selected_server


xlo.log("login_test.py loading")

def AddDataHub(datahub):    
    global _datahub
    _datahub = datahub

    for svr in _servers:
        datahub.add_credentials(svr["name"], svr["user"], svr["pass"])

#Save credentials with hashed passwords. 
def save_credentials(filename=None):
    #If no filenmame is given, use default in user appdata folder
    if filename is None:
        import os
        appdata = os.getenv('APPDATA')
        filename = os.path.join(appdata, 'dataspace_credentials.txt')

    #Get an uuid of some sort from the machine to use as salt
    import uuid
    machine_id = str(uuid.getnode())


    with open(filename, 'w') as f:
        for svr in _servers:
            #encrypt the password 
            hashed_pass = xor_encrypt(svr["pass"].encode(),machine_key()).hex()
            f.write(f"{svr['name']},{svr['user']},{hashed_pass}\n")



def machine_key():
    node = str(uuid.getnode()).encode()
    return hashlib.sha256(node).digest()  # 32 bytes

def xor_encrypt(data: bytes, key: bytes) -> bytes:
    return bytes([d ^ key[i % len(key)] for i, d in enumerate(data)])

def xor_decrypt(data: bytes, key: bytes) -> bytes:
    return xor_encrypt(data, key)  # samma operation

def old_load_credentials(filename=None):
    global _servers
    #If no filenmame is given, use default in user appdata folder
    if filename is None:
        import os
        appdata = os.getenv('APPDATA')
        filename = os.path.join(appdata, 'dataspace_credentials.txt')

    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
            _servers = []
            for line in lines:
                name, user, enc_pass = line.strip().split(',')
                dec_pass = xor_decrypt(bytes.fromhex(enc_pass), machine_key()).decode()
                _servers.append({"name": name, "user": user, "pass": dec_pass})
    except FileNotFoundError:
        xlo.log("Credentials file not found, starting with empty server list.")
    except Exception as e:
        xlo.log(f"Error loading credentials: {e}")

def load_credentials(filename=None):
    global _servers

    # Bestäm sökväg
    if filename is None:
        import os
        appdata = os.getenv('APPDATA')
        filename = os.path.join(appdata, 'dataspace_credentials.txt')

    try:
        with open(filename, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        _servers = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split(',')
            if len(parts) != 3:
                xlo.log(f"Ignoring invalid credential line: {line!r}")
                continue

            name, user, enc_pass = parts
            dec_pass = None  # default if decoding fails

            # Försök dekryptera lösenordet
            try:
                raw = bytes.fromhex(enc_pass)            # kan faila om hex är odd/korrupt
                decrypted = xor_decrypt(raw, machine_key())
                dec_pass = decrypted.decode("utf-8")     # kan faila om key är annorlunda
            except Exception as err:
                xlo.log(f"Password decode failed for server '{name}': {err}")
                dec_pass = None

            _servers.append({"name": name, "user": user, "pass": dec_pass})

        # Efter att alla servrar laddats → be om nytt lösenord för de som saknar
        for srv in _servers:
            if srv["pass"] is None:
                xlo.log(f"Lösenord saknas/korrumperat för '{srv['name']}'. Ber användaren mata in nytt.")
                ask_for_password(srv)

    except FileNotFoundError:
        xlo.log("Credentials file not found, starting with empty server list.")
        _servers = [{"name": "New", "user": "", "pass": ""}]

    except Exception as e:
        xlo.log(f"Error loading credentials: {e}")
        # fallback if serious error, to avoid Excel crashing
        _servers = [{"name": "New", "user": "", "pass": ""}]


#Load upon start.
if storecredentials:
    load_credentials()

#Select the first server by default
if _servers:
    selected_server = _servers[0]["name"]

def say_hi(ctrl):
    xlo.log("Ribbon button clicked")

def GetSelectedServer():
    """Returnerar den valda servern från _servers listan"""
    global selected_server
    global _server

    if selected_server is None:
        return None

    for srv in _servers:
        if srv["name"] == selected_server:
            return srv

    return None

def SetSelectedServer(name):
    """Sätter den valda servern"""
    global selected_server
    selected_server = name

def open_add_server_window(ctrl=None):
    """Öppnar ett litet fönster för att lägga till server"""

    # if selected server is not none or the new fill in the fields
    selected = GetSelectedServer()

    if selected is not None and selected["name"] != "New":
        default_server = selected["name"]
        default_user = selected["user"]
        default_pass = selected["pass"]
    else:
        default_server = ""
        default_user = ""
        default_pass = ""


    win = tk.Tk()
    win.title("Lägg till server")
    win.geometry("250x150")

    tk.Label(win, text="Server:").grid(row=0, column=0, sticky="e")
    tk.Label(win, text="Användare:").grid(row=1, column=0, sticky="e")
    tk.Label(win, text="Lösenord:").grid(row=2, column=0, sticky="e")

    e_server = tk.Entry(win)
    e_user = tk.Entry(win)
    e_pass = tk.Entry(win, show="*")

    # Fyll i fälten om vi redigerar en befintlig server
    if selected is not None:
        e_server.insert(0, default_server)
        e_user.insert(0, default_user)
        e_pass.insert(0, default_pass)

    e_server.grid(row=0, column=1)
    e_user.grid(row=1, column=1)
    e_pass.grid(row=2, column=1)

    def add_server():
        server = e_server.get().strip()
        user = e_user.get().strip()
        if not server or not user:
            messagebox.showwarning("Fel", "Server och användare måste anges.")
            return
        #Lägg till server i listan enligt formatet först i listan
        if selected is not None and selected["name"] != "New":
            selected["name"] = server
            selected["user"] = user
            selected["pass"] = e_pass.get().strip()
        else:
            _servers.insert(0, {"name": server, "user": user, "pass": e_pass.get().strip()})
        #_servers.append({"name": server, "user": user, "pass": e_pass.get().strip()})
        SetSelectedServer(server)

        if storecredentials:
            save_credentials()

        if _datahub is not None:
            _datahub.add_credentials(server, user, e_pass.get().strip())

        _excelgui.invalidate("serverlist")

        xlo.log(f"Server tillagd: {server}")
        win.destroy()

    tk.Button(win, text="Lägg till", command=add_server).grid(
        row=3, column=0, columnspan=2, pady=8
    )

    win.mainloop()


def dropdown_changed(ctrl, text):
    """När användaren väljer en server i dropdownen"""
    xlo.log(f"Vald server: {text}")
    #Spara valet till global variable
    global _selected_server
    global selected_server
    selected_server = text


def get_servers(ctrl,n):
    """Returnerar servernamn till dropdownen"""
    # Ribbon dropdown måste returnera en lista av tuples (id, label)


    if n >= len(_servers):
        return None
    
    return _servers[n]["name"]

def delete_server(ctrl):
    """Tar bort den valda servern från listan"""
    global selected_server
    global _servers

    if selected_server is None or selected_server == "New":
        xlo.log("Ingen server vald att ta bort.")
        return

    for i, srv in enumerate(_servers):
        if srv["name"] == selected_server:
            del _servers[i]
            xlo.log(f"Server borttagen: {selected_server}")
            selected_server = None
            if _servers:
                selected_server = _servers[0]["name"]
            if storecredentials:
                save_credentials()
            _excelgui.invalidate("serverlist")

            try:
               _datahub.delete_credentials(selected_server)
            except Exception as e:
                xlo.log(f"Error deleting credentials for {selected_server}: {e}")
            return

    xlo.log("Vald server hittades inte i listan.")

def get_selected_server_index(ctrl):
    """Returnerar index för vald server i dropdownen"""
    # Här returnerar vi alltid 0 som exempel

    if selected_server is None:
        return 0
    for i, srv in enumerate(_servers):
        if srv["name"] == selected_server:
            return i
    return 0

xml=r'''
<customUI xmlns="http://schemas.microsoft.com/office/2009/07/customui">
  <ribbon>
    <tabs>
      <tab id="serverTab" label="Serverhantering" insertAfterMso="TabHome">
        <group id="serverGroup" label="Servrar">
          <dropDown id="serverDrop"
                    getItemCount="get_servers_count"
                    getItemLabel="get_servers_label"
                    onChange="dropdown_changed"
                    label="Servrar" />
          <button id="addServer" label="Lägg till server" size="large" onAction="open_add_server_window" imageMso="HappyFace"/>
        </group>
      </tab>
    </tabs>
  </ribbon>
</customUI>
'''

xml2 = r'''
   <customUI xmlns="http://schemas.microsoft.com/office/2009/07/customui">
       <ribbon>
           <tabs>
               <tab id="customTab2" label="Server management" insertAfterMso="tab">
               
                   <group id="customGroup" label="Servers">

                       <comboBox id="serverlist" label="Servers" onChange="dropdown_changed" getItemCount="get_servers_count" getItemLabel="get_servers_label" getText="cb_text" >
                       </comboBox>
                       <button id="addServer" label="Edit" size="large" onAction="add_server" imageMso="MasterDocumentCreateSubdocument" />
                       <button id="deleteserver" label="Remove" size="large" onAction="deleteserver" imageMso="MasterDocumentUnlinkSubdocument" />
                   </group>
               </tab>
           </tabs>
       </ribbon>
   </customUI>
   '''



map = {
        "deleteserver": delete_server,
        "add_server": open_add_server_window,
        "dropdown_changed": dropdown_changed,
        "get_servers_count": lambda ctrl: len(_servers) or 1,
        "get_servers_label": get_servers,
        "dd_selected_index": get_selected_server_index,
        "cb_text": lambda ctrl: _servers[0]["name"] if _servers else ""
    }

_excelgui = xlo.ExcelGUI(
    ribbon=xml2,
    funcmap=map
)

xlo.log("login_test.py loaded and ExcelGUI executed")
