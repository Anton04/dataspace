import xloil as xlo
import asyncio
from dataspace_client import DataHub
import json
from fnmatch import fnmatch
import os, tempfile
from urllib.parse import urlparse
from urllib.request import urlretrieve
import login_interface
import figures
import hashlib
import json_formatting

 
# Single RtdServer shared by all topics
_rtd_server = xlo.RtdServer()

# Global DataHub client instance
datahub = DataHub()

login_interface.AddDataHub(datahub)

published_values = {}


# Add MQTT credentials
#datahub.add_credentials("mqtt://iot.digivis.se", "test", "test")

@xlo.func
def caller_address() -> str:
    cell = xlo.Caller()
    address = cell.address()   # MUST be called
    return address

@xlo.func
def getcellname() -> str:
    address = caller_address()
    name = address.split("]")[-1]  # Ta bort ev. bladnamn
    return name


@xlo.func
def stable_hash(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")  # gör om sträng → bytes
    elif not isinstance(data, (bytes, bytearray)):
        raise TypeError("stable_hash requires str or bytes")

    return hashlib.sha256(data).hexdigest()

#Create cash path
@xlo.func
def get_cache_path(url)-> str:

    #Get fileending fex .glb .jpg etc
    file_ending = url.rsplit(".", 1) if "." in url else ("", "")
    file_ending = "." + file_ending[1] if len(file_ending) > 1 else ""
   

    #Create cache directory if not exists
    cache_dir = os.path.join(tempfile.gettempdir(), "dataspace_cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    #Create long hash from url that can be used as filename
    hash_name = str(stable_hash(url)) + file_ending
    file_path = os.path.join(cache_dir, f"{hash_name}")
    return file_path


#  Cashe exists. Checks if the url is cashed already with the same content
def cache_exists(url: str, bindata: bytes) -> bool:
    file_path = get_cache_path(url)
    return cache_file_exists(file_path, bindata)

# Cashe exists. Checks if the file exists with the same content
def cache_file_exists(file_path: str) -> bool:
    return os.path.exists(file_path)

# cashe exists.
def cashe_exists(url: str) -> bool:
    file_path = get_cache_path(url)
    return cache_file_exists(file_path)

# Check if cache file exists with same content
def cache_file_matches(file_path: str, bindata: bytes) -> bool:
    if os.path.exists(file_path):
        #Check if same size
        if os.path.getsize(file_path) == len(bindata):
            #check if same content
            with open(file_path, "rb") as f:
                existing_data = f.read()
            if existing_data == bindata:
                return True
    return False

# Save cache file if we have the temp path and bindata
def save_cache_file(file_path: str, bindata: bytes):
    with open(file_path, "wb") as f:
        f.write(bindata)

# Cache the data from url with bindata
def save_cashe(url: str, bindata: bytes):
    file_path = get_cache_path(url)
    save_cache_file(file_path, bindata)

# Hjälpfunktion: hämtar DocumentProperties COM-objektet
def _get_doc_props():
    app_com = xlo.app().to_com()
    wb = app_com.ActiveWorkbook
    return wb.CustomDocumentProperties


def _find_prop(props, key):
    key_lower = key.lower()
    for prop in props:
        if prop.Name.lower() == key_lower:
            return prop
    return None


@xlo.func
def save_hash(hash_key: str, hash_value: str):
    props = _get_doc_props()

    # Finns redan?
    existing = _find_prop(props, hash_key)
    if existing:
        existing.Value = hash_value
        return f"Updated hash '{hash_key}'"

    # Skapa ny (type 4 = string)
    props.Add(hash_key, False, 4, hash_value)
    return f"Saved hash '{hash_key}'"


@xlo.func
def load_hash(hash_key: str):
    props = _get_doc_props()

    existing = _find_prop(props, hash_key)
    if existing:
        return existing.Value

    return "No hash saved"


@xlo.func
def get_hash_keys():
    props = _get_doc_props()
    return [prop.Name for prop in props]



@xlo.func
def checkworkbookhashandupdate(hash_key: str, hash_value: str) -> bool:
    """
    Return True if hash matches saved value. 
    If different, update and return False.
    """
    saved_hash = load_hash(hash_key)

    if saved_hash == hash_value:
        return True

    save_hash(hash_key, hash_value)
    return False

# ---------- Handler registry ----------
_FILE_HANDLERS = {}
def register_handler(pattern: str, func):
    _FILE_HANDLERS[pattern.lower()] = func


#Find a figure by name
def find_figures_by_name(name: str):
    app = xlo.app()
    existing_shapes = [shape for shape in app.ActiveSheet.Shapes if shape.Name == name]
    return existing_shapes

# ---------- Handlers ----------
def _handle_glb(url, bindata):
    cell = xlo.Caller()

    rng = cell.range
    com_range = rng.to_com()

    if com_range:
        left = com_range.Left
        top = com_range.Top + com_range.Height
    else:
        left = 60     # fallback värde
        top = 60
    width = 300
    height = 300


    tmp_path = get_cache_path(url)

    hash = str(stable_hash(bindata))

    hashmatch = checkworkbookhashandupdate(tmp_path, hash)

    #save_hash(tmp_path, str(stable_hash(bindata)))

    #Check if exist
    #cash_exists = cache_file_exists(tmp_path)
    #datauptodate =  cache_file_matches(tmp_path, bindata)
    
    #tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    
    figurename = url + getcellname()
    #Check if a shape with the same name already exists
    existing_shapes = find_figures_by_name(figurename)

    if existing_shapes:
        if hashmatch:
            return f"3D model shape '{url}' is already up to date."

    save_cache_file(tmp_path, bindata)
    app = xlo.app()
     
    if existing_shapes:
        for shape in existing_shapes:
            #Save position and size
            left = shape.Left
            top = shape.Top
            width = shape.Width
            height = shape.Height
            shape.Delete()

            shp = app.ActiveSheet.Shapes.Add3DModel(tmp_path, left, top, width, height)
            shp.Left = left
            shp.Top = top
            shp.Width = width
            shp.Height = height
            shp.Name = figurename
        return f"Updated existing 3D model shape(s) with name '{url}'"
      
        #return f"3D model shape '{shape.Name}' updated."

    shp = app.ActiveSheet.Shapes.Add3DModel(tmp_path, left, top, width, height)

    shp.Name = figurename
    return f"Inserted 3D model from {url or '(no url)'} → {shp.Name}"

def _handle_image(url, bindata, ext):

    cell = xlo.Caller()

    rng = cell.range
    com_range = rng.to_com()

    if com_range:
        left = com_range.Left
        top = com_range.Top + com_range.Height
    else:
        left = 60     # fallback värde
        top = 60
        
    width = -1
    height = -1


    tmp_path = get_cache_path(url)

    hash = str(stable_hash(bindata))

    hashmatch = checkworkbookhashandupdate(tmp_path, hash)
    
    
    figurename = url + getcellname()

    #Check if a shape with the same name already exists
    existing_shapes = find_figures_by_name(figurename)

    if hashmatch and existing_shapes:
        return f"Image '{url}' is already up to date. (hash match)"
    
    save_cache_file(tmp_path, bindata)
    app = xlo.app()
     
    if existing_shapes:
        for shape in existing_shapes:
            #Save position and size
            left = shape.Left
            top = shape.Top
            width = shape.Width
            height = shape.Height
            shape.Delete()

            shp = app.ActiveSheet.Shapes.AddPicture(tmp_path,0,-1, left, top, width, height)
            shp.Left = left
            shp.Top = top
            shp.Width = width
            shp.Height = height
            shp.Name = figurename
        return f"Updated existing image shape(s) with name '{url}'"
      
        #return f"3D model shape '{shape.Name}' updated."

    shp = app.ActiveSheet.Shapes.AddPicture(tmp_path,0,-1, left, top, width, height)

    max_size = 300

    if shp.Width > max_size or shp.Height > max_size:
        scale_w = max_size / shp.Width
        scale_h = max_size / shp.Height
        scale = min(scale_w, scale_h)
        shp.Width = shp.Width * scale
        shp.Height = shp.Height * scale

    shp.Name = figurename
    return f"Inserted image from {url or '(no url)'} → {shp.Name}"


  

# ---------- NEW: directory/topic handler ----------


# Function to trigger start of cells calculations on load
def test_cell_edit():
    xl = xlo.app()
    sheet = xl.ActiveSheet
    rng = sheet.Range("A1")
    
    original = rng.Value         # 1. Läs originalvärdet
    print("Original:", original)
    
    rng.Value = "TEMP VÄRDE"     # 2. Ändra cellen
    print("Ändrade till TEMP")
    
    # ... valfri logik här ...
    
    rng.Value = original         # 3. Återställ
    print("Återställt till original:", original)






import json

def _handle_directory(url, bindata):
    """
    URL ends with '/': return a vertical spill.
    Row 1 = URL
    Rows below = entries prefixed with 📁 (endswith '/')
                 or 📄 (otherwise)
    """
    # Decode payload safely
    try:
        text = bindata.decode("utf-8", errors="replace").strip()
    except Exception:
        return [[url]]

    if not text:
        return [[url]]

    def label_entry(entry):
        # Extract a displayable name
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = (entry.get("name")
                    or entry.get("path")
                    or entry.get("url")
                    or entry.get("id"))
            if not isinstance(name, str):
                name = json.dumps(entry, ensure_ascii=False)
        else:
            name = str(entry)

        emoji = "📁" if isinstance(name, str) and name.endswith("/") else "📄"
        return f"{emoji} {name} "

    rows = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            rows = [[label_entry(item)] for item in data]
        elif isinstance(data, dict):
            # Single object: show one labeled row
            rows = [[label_entry(data)]]
        else:
            rows = [[label_entry(str(data))]]
    except Exception:
        # Not JSON → split by lines and label each
        lines = [ln for ln in text.splitlines() if ln.strip()]
        rows = [[label_entry(ln)] for ln in lines] if lines else [[label_entry(text)]]

    return [[url]] + rows




# Existis in newer datahub versions and can be removed later
def check_credentials(url: str):
        global datahub

        #Extract server adress from url
        parsed_url = urlparse(url)
        server_address = parsed_url.hostname
        return datahub.credentials.get(server_address) != None


# Defaults
register_handler("*/", _handle_directory)
register_handler("*.glb",  _handle_glb)
register_handler("*.jpg",  lambda url, b: _handle_image(url, b, ".jpg"))
register_handler("*.jpeg", lambda url, b: _handle_image(url, b, ".jpg"))
register_handler("*.png",  lambda url, b: _handle_image(url, b, ".png"))


# ---------- Main ----------


@xlo.func
def sync_data(topic: str, value=None, formatter=None):
    """
    Syncs live dataspace values to Excel using RTD.
    - Preserves your publish-on-change logic
    - Prevents duplicate subscriptions
    - Prevents reexecution loops by caching RTD objects
    """
    #print(f"Sync data called for topic: {topic} with value: {value}")

    cell = xlo.Caller()

    #None if no caller
    address = cell.address() if cell else None   # MUST be called
   

    # --- Publish updated values (your original logic preserved) ---
    if value is not None:
        
        if cell:
            

            # First-time publish at this cell
            if address not in published_values:
                print(f"Initial publish to {topic}: {value}")
                published_values[address] = value
                datahub.Publish(topic, value)
            else:
                # Only publish when changed
                if published_values[address] != value:
                    published_values[address] = value
                    print(f"Publishing updated value to {topic}: {value}")
                    datahub.Publish(topic, value)
                else:
                    print(f"No change for {topic}. Not publishing.")
        else:
            print("Warning: No caller cell found.")

    # --- Credential check ---
    if not check_credentials(topic):
        return "No credentials found. Please add credentials."

    if not topic:
        return "No topic specified"

    # --- Ensure RTD publisher exists ---
    value = _rtd_server.peek(topic)

    #Print value
    print(f"RTD value for {topic}: {value} \n")

    if value is None:
        #print(f"Creating LiveDataPublisher for {topic}")
        pub = LiveDataPublisher(topic, formatter)
        _rtd_server.start(pub)
        #_rtd_server.publish(topic, "NaN")

    else:
        #print(f"LiveDataPublisher for {topic} already exists.")
        pass

    #if pub._subscribed is False:
    #    print(f" Not subscribed.")
    #    _rtd_server.start(pub)

    #print

    return _rtd_server.subscribe(topic)


@xlo.func
def get_from_dataspace(url: str):
    """
    Fetch via datahub.Get(url, handler=None).
    - Ensures credentials have been added before trying to call Get().
    - If URL ends with a registered extension (*.glb, *.jpg, *.png) -> use handler.
    - Otherwise, return decoded text or JSON pretty-printed if object.
    """
 

    if not url:
        return "No URL provided"

    # --- Ensure credentials / login first ---
    if not check_credentials(url):
        return "Not logged in. Add credentials server management tab."

   

    # --- Try fetching data ---
    try:
        print(f"[Dataspace] Calling datahub.Get('{url}') ...")
        res = datahub.Get(url, handler=None)
    except Exception as e:
        return f"Error calling datahub.Get: {e}"

    if res is None:
        return f"No data returned from {url}"

    # --- Normalize to bytes when possible ---
    if isinstance(res, str):
        data_bytes = res.encode("utf-8", errors="replace")
    elif isinstance(res, (bytes, bytearray)):
        data_bytes = res
    elif hasattr(res, "read"):
        data_bytes = res.read()
    else:
        try:
            import json
            return json.dumps(res, indent=2, ensure_ascii=False)
        except Exception:
            return str(res)

    # --- Handler dispatch ---
    # 1) Directory/topic handler for URLs ending with '/'
    if isinstance(url, str) and url.endswith("/"):
        if "*/" in _FILE_HANDLERS:
            try:
                return _FILE_HANDLERS["*/"](url, data_bytes)
            except Exception as e:
                return f"Handler error (*/): {e}"
        

    ext = os.path.splitext(url.split("?", 1)[0])[1].lower() if isinstance(url, str) else ""
    if ext:
        for pattern, func in _FILE_HANDLERS.items():
            if fnmatch(ext, pattern):
                try:
                    return func(url, data_bytes)
                except Exception as e:
                    return f"Handler error ({pattern}): {e}"

    # --- Fallback: return text ---
    try:
        text = data_bytes.decode("utf-8", errors="replace").strip()
        return text if text else f"(empty response from {url})"
    except Exception:
        return f"Binary data ({len(data_bytes)} bytes)"
    

@xlo.func
def fill_three_below(v1="A", v2="B", v3="C"):


    return ["fill_tree_below","A","B","C"] #Down

@xlo.func
def fill_three_right():

    return [["fill_tree_below_2","A","B","C"]] #Right


import re

def _to_str(val):
    if val is None:
        return ""
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    return str(val)

def _walk(obj, level, rows):
    """
    Fyller 'rows' med rader. Varje rad börjar med 'level' tomma celler,
    därefter key och ev. value i två intilliggande celler.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = _to_str(k)
            if isinstance(v, (dict, list)):
                # Rad med bara nyckel (ingen { eller [ visas)
                rows.append([""] * level + [key, ""])
                _walk(v, level + 1, rows)
            else:
                rows.append([""] * level + [key, _to_str(v)])
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                # Visa en "rad för post" utan parenteser
                rows.append([""] * level + [f"[{i}]", ""])
                _walk(item, level + 1, rows)
            else:
                # Primitivt listelement: en cell för värdet (ingen nyckel)
                rows.append([""] * level + [_to_str(item)])
    else:
        # Fritt primitivt värde
        rows.append([""] * level + [_to_str(obj)])

@xlo.func
def json_to_cells_pretty(json_text: str):
    """
    Pretty till celler:
    - Indrag = tomma celler
    - 'key' och 'value' i två celler bredvid varandra
    - Inga { } [ ] skrivs ut
    """
    if json_text is None or str(json_text).strip() == "":
        return [["(empty)"]]

    try:
        obj = json.loads(json_text)
    except Exception as e:
        # Om det inte är giltig JSON – returnera texten som en rad
        return [[str(json_text)]]

    rows = []
    _walk(obj, level=0, rows=rows)

    # Rektangulisera (Excel kräver lika många kolumner per rad)
    max_cols = max(len(r) for r in rows) if rows else 1
    for r in rows:
        if len(r) < max_cols:
            r.extend([""] * (max_cols - len(r)))

    return rows

@xlo.func()
def version():
    return 1.2



@xlo.func(macro=True)
def json_to_sheet_here(json_text: str):
    """
    Skriv JSON som tabell under den aktiva cellen.
    Kräver inte xlo.caller(); använder xlo.app().ActiveCell.
    """
    try:
        obj = json.loads(json_text)
    except Exception as e:
        return f"JSON error: {e}"

    # Bygg rader: indrag = tomma celler, key|value i två celler
    rows = []
    def _to_str(v):
        if v is None: return ""
        if isinstance(v, bool): return "TRUE" if v else "FALSE"
        return str(v)

    def _walk(o, lvl=0):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    rows.append([""]*lvl + [_to_str(k), ""])
                    _walk(v, lvl+1)
                else:
                    rows.append([""]*lvl + [_to_str(k), _to_str(v)])
        elif isinstance(o, list):
            for i, it in enumerate(o):
                if isinstance(it, (dict, list)):
                    rows.append([""]*lvl + [f"[{i}]", ""])
                    _walk(it, lvl+1)
                else:
                    rows.append([""]*lvl + [_to_str(it)])
        else:
            rows.append([""]*lvl + [_to_str(o)])

    _walk(obj)

    # Rektangulisera
    max_cols = max(len(r) for r in rows) if rows else 1
    for r in rows:
        r.extend([""] * (max_cols - len(r)))

    # Skriv under aktiv cell (COM, fungerar i alla xlOil-versioner)
    app = xlo.app()
    ws = app.ActiveSheet
    ac = app.ActiveCell
    sr, sc = ac.Row + 1, ac.Column
    er, ec = sr + len(rows) - 1, sc + max_cols - 1
    ws.Range(ws.Cells(sr, sc), ws.Cells(er, ec)).Value = rows
    return f"Wrote {len(rows)} rows starting at R{sr}C{sc}"


@xlo.func(macro=True)
def json_to_sheet(json_text: str):
    """Skriver JSON som tabell i arket, redigerbart"""
    try:
        data = json.loads(json_text)
    except Exception as e:
        return f"JSON error: {e}"

    ws = xlo.app().ActiveWorksheet()
    start_row = xlo.caller().row + 1
    start_col = xlo.caller().column

    rows = []
    def flatten(obj, level=0):
        if isinstance(obj, dict):
            for k,v in obj.items():
                if isinstance(v, (dict, list)):
                    rows.append([""]*level + [k])
                    flatten(v, level+1)
                else:
                    rows.append([""]*level + [k, str(v)])
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                rows.append([""]*level + [f"[{i}]"])
                flatten(item, level+1)
        else:
            rows.append([""]*level + [str(obj)])

    flatten(data)

    max_cols = max(len(r) for r in rows)
    for r in rows:
        r.extend([""] * (max_cols - len(r)))

    ws.range(start_row, start_col,
             start_row+len(rows)-1, start_col+max_cols-1).value = rows

    return f"Wrote {len(rows)} rows"




def _ensure_local_image(path_or_url: str) -> str:
    """
    Returnerar en lokal filväg till bilden. Laddar ner om det är en http(s)-URL.
    """
    if not path_or_url:
        raise ValueError("Empty image path/URL")

    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        suffix = os.path.splitext(parsed.path)[1] or ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        urlretrieve(path_or_url, tmp.name)
        return tmp.name
    # Lokal fil
    if not os.path.isfile(path_or_url):
        raise FileNotFoundError(f"File not found: {path_or_url}")
    return path_or_url

@xlo.func
def insert_image_from_cell(path_or_url: str,
                           left: float = 60.0, top: float = 60.0,
                           width: float = 0.0, height: float = 0.0,
                           lock_aspect: bool = True,
                           name: str = "") -> str:
    """
    Infogar en bild (lokal fil eller http/https) på aktivt blad.
    - width/height = 0 => Excel använder bildens naturliga storlek.
    - lock_aspect True => behåll bildens proportioner om både width och height anges (>0),
      Excel justerar då den ena sidan.
    - name kan sättas för att döpa formen.

    Exempel i Excel:
      =insert_image_from_cell(A1, 100, 120, 300, 0, TRUE, "Logo")
    """
    img_path = _ensure_local_image(path_or_url)

    app = xlo.app()
    sheet = app.ActiveSheet

    # Välj API: AddPicture (fungerar brett). Signatur:
    # AddPicture(FileName, LinkToFile, SaveWithDocument, Left, Top, Width, Height)
    # LinkToFile=0 (False), SaveWithDocument=-1 (True)
    # width/height = -1 => ”original size”
    W = width if width and width > 0 else -1
    H = height if height and height > 0 else -1

    shp = sheet.Shapes.AddPicture(img_path, 0, -1, left, top, W, H)

    # Lås proportioner om begärt
    try:
        shp.LockAspectRatio = -1 if lock_aspect else 0
    except Exception:
        pass

    # Döp formen om ett namn gavs
    if name:
        try:
            shp.Name = name
        except Exception:
            pass

    # Sätt alt-text (bra för senare identifiering)
    try:
        shp.AlternativeText = f"Inserted from {path_or_url}"
    except Exception:
        pass

    return f"Inserted image shape: {shp.Name}"

@xlo.func
def insert_glb_from_cell(model_path: str, left: float = 100, top: float = 100,
                         width: float = 300, height: float = 300):
    """Laddar in en GLB-modell från sökväg given i cell."""
    if not os.path.isfile(model_path):
        return f"File not found: {model_path}"

    app = xlo.app()
    sheet = app.ActiveSheet
    shp = sheet.Shapes.Add3DModel(model_path, left, top, width, height)
    return f"Inserted 3D model '{shp.Name}' from {model_path}"



@xlo.func
def load_3d_model(model_path: str):

    left: float = 60.0
    top: float = 60.0
    width: float = 300.0
    height: float = 300.0

    file = "D:\Downloads\Earth_2K.glb"

    # 2) Get the Excel objects via xloil (on main thread)
    app = xlo.app()
    sheet = app.ActiveSheet

    shp = sheet.Shapes.Add3DModel(file, left, top, width, height)

    return "Körd!"

# @xlo.func
# def AddUserCredentials(server: str, username:str,password:str):
#    
    
#     datahub.add_credentials(server, username, password)

#     #Bugfix: Reconnect to the server to apply the new credentials
#     #datahub.servers[server].reconnect()

#  
#     print(f"Credentials added for {server}")

#     #Add timestamp to the credentials
#     timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     return "Credentials added at " + timestamp

@xlo.func
def subscribe(topic: str):
    """
    Excel function that subscribes to an MQTT topic and updates the cell in real time.
    - topic: The MQTT topic to subscribe to.

    Example usage in Excel:
      =subscribe_livedata("mqtt://iot.digivis.se/datadirectory/TestArea/signalA")
    """
    return subscribe_livedata(topic)


@xlo.func
def subscribe_livedata(topic: str):
    """
    Excel function that subscribes to an MQTT topic and updates the cell in real time.
    - topic: The MQTT topic to subscribe to.

    Example usage in Excel:
      =subscribe_livedata("mqtt://iot.digivis.se/datadirectory/TestArea/signalA")
    """


    if not check_credentials(topic):
        return "No credentials found. Please use server management tab to add them."

    if topic == None or topic == "":
        return "No topic specified"

    #if topic not in _publishers:
    if _rtd_server.peek(topic) is None:

        print(f"Creating LiveDataPublisher for {topic}")
        pub = LiveDataPublisher(topic)
        _rtd_server.start(pub)
        _rtd_server.publish(topic, "NaN - waiting for data...")

    return _rtd_server.subscribe(topic)

from datetime import datetime

@xlo.func
def publish_live_data(topic: str, payload: str,retain: bool=False):
    """
    Excel function to publish data to a topic via DataHub, with timestamp.
    
    Example usage in Excel:
      =publish_live_data("mqtt://iot.digivis.se/datadirectory/TestArea/signalA", "Hello World")
    """



    if not check_credentials(topic):
        return "No credentials found. Please use server management tab to add them."

    if not topic:
        return "No topic specified"
    
    if not payload:
        return "No payload specified"

    try:
        datahub.Publish(topic, payload,retain)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Published data to {topic}: {payload}")
        return f" {payload} published at {timestamp}"
    except Exception as e:
        print(f"Error publishing to {topic}: {e}")
        return f"Failed to publish: {e}"

@xlo.func
def generate_series(start: float, step: float, count: int):
    """
    Generates a series of numbers starting from 'start', 
    increasing by 'step', with 'count' values.
    
    Example usage in Excel:
    =generate_series(1, 2, 5)
    """
    return [start + i * step for i in range(count)]

@xlo.func
def generate_matrix(rows: int, cols: int, start: float = 1, step: float = 1):
    """
    Generates a matrix with the given number of rows and columns.
    Each cell increases by 'step', starting from 'start'.

    Example usage in Excel:
    =generate_matrix(3, 4, 10, 2)
    """
    return [
        [start + (i * cols + j) * step for j in range(cols)]
        for i in range(rows)
    ]

class LiveDataPublisher(xlo.RtdPublisher):
    def __init__(self, topic: str,formatter=None):
        """
        A publisher that subscribes to an MQTT topic via `DataHub`
        and updates Excel with real-time data.
        """
        super().__init__()
        self._topic = topic 
        self._formatter = formatter


        #Slice the topic to get the subtopic
        
        self._maintopic = topic
        self._subtopic = None


        self._subscribed = False

        print(f"LiveDataPublisher created for: \n{self._topic} \n")
        
       

    def connect(self, num_subscribers: int):
        """Called when at least one Excel cell subscribes."""
        print(f"LiveDataPublisher connect called for {self._topic} with {num_subscribers} subscribers.\n")

        #_rtd_server.publish(self.topic(),"NaN") 

        if num_subscribers > 0 and not self._subscribed:
            print(f"Subscribing to {self._topic} via DataHub... \n")
            
            datahub.Subscribe(self._topic, self.on_message)
            self._subscribed = True

    def on_message(self, topic, payload,msg_type):
        """
        Called when a new message arrives from the MQTT broker.
        """

        #topic = "mqtt://iot.digivis.se/" + topic

        #print(f"Received MQTT data for {topic}: {payload}")

        #Check if parsed json or bindary
        if isinstance(payload, (bytes, bytearray)):
            decoded_payload = payload.decode("utf-8")
        else:
            decoded_payload = payload
            
        #if self.topic() == "dataspace/TestArea/test.json":  
        



        # Convert the payload to a string
        #if isinstance(payload, bytes):
            


        #self.publish(payload)
        if self._formatter:
            formatted_payload = self._formatter(decoded_payload)
        #Check if object
        elif isinstance(decoded_payload, (dict, list)):
            formatted_payload = json.dumps(decoded_payload, indent=2, ensure_ascii=False)
        else:
            formatted_payload = decoded_payload

        if _rtd_server.peek(self.topic()) == formatted_payload:
            #No change
            return
        
        print(f"RTD Publishing data for {self._topic}: {formatted_payload} {msg_type}")

        _rtd_server.publish(self.topic(), formatted_payload) 

    def disconnect(self, num_subscribers: int):

        print(f"LiveDataPublisher disconnect called for {self._topic} with {num_subscribers} subscribers.")

        

        if num_subscribers == 0:
            print(f"Stopping subscription to {self._topic}")
            self._subscribed = False
            datahub.Unsubscribe(self._topic, self.on_message)
            _rtd_server.publish(self.topic(),None)
            return True
        else:
            return False


    def stop(self):
        """
        Stops the subscription.
        """
        print(f"Stopping subscription to {self._topic}")

        #_rtd_server.publish(self.topic(), "-")
        self._subscribed = False  # No explicit unsubscribe function in DataHub?
        datahub.Unsubscribe(self._topic, self.on_message)
        _rtd_server.publish(self.topic(),None)

    def topic(self):
        """
        Returns the associated topic name.
        """
        return self._topic

    def done(self):
        """
        Returns True if this publisher is finished and should be destroyed.
        """
        return not self._subscribed  # Returns True when unsubscribed

import time

