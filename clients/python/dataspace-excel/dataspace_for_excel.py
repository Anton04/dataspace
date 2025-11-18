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

# Single RtdServer shared by all topics
_rtd_server = xlo.RtdServer()

# Global DataHub client instance
datahub = DataHub()

login_interface.AddDataHub(datahub)

# Add MQTT credentials
#datahub.add_credentials("mqtt://iot.digivis.se", "test", "test")




# ---------- Handler registry ----------
_FILE_HANDLERS = {}
def register_handler(pattern: str, func):
    _FILE_HANDLERS[pattern.lower()] = func

# ---------- Handlers ----------
def _handle_glb(url, bindata):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
    with open(tmp.name, "wb") as f:
        f.write(bindata)
    app = xlo.app()
    shp = app.ActiveSheet.Shapes.Add3DModel(tmp.name, 60, 60, 300, 300)
    return f"Inserted 3D model from {url or '(no url)'} → {shp.Name}"

def _handle_image(url, bindata, ext):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    with open(tmp.name, "wb") as f:
        f.write(bindata)
    app = xlo.app()
    shp = app.ActiveSheet.Shapes.AddPicture(tmp.name, 0, -1, 60, 60, -1, -1)
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
        _rtd_server.publish(topic, "NaN")

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
    def __init__(self, topic: str):
        """
        A publisher that subscribes to an MQTT topic via `DataHub`
        and updates Excel with real-time data.
        """
        super().__init__()
        self._topic = topic 


        #Slice the topic to get the subtopic
        parts = topic.split("[")
        self._maintopic = parts[0]
        self._subtopic = None

        if len(parts) > 1:
            self._subtopic = parts[1].split("]")[0]

        self._subscribed = False

        print(f"LiveDataPublisher created for {self._topic}")
        print(f"Main topic: {self._maintopic}")
        print(f"Subtopic: {str(self._subtopic)}")

    def connect(self, num_subscribers: int):
        """ 
        Called when at least one Excel cell subscribes to this topic.
        """
        if not self._subscribed:
            print(f"Subscribing to {self._topic} via DataHub...")
            datahub.Subscribe(self._maintopic, self.on_message)  # Subscribe using DataHub
            self._subscribed = True

    def on_message(self, topic, payload,private):
        """
        Called when a new message arrives from the MQTT broker.
        """

        topic = "mqtt://iot.digivis.se/" + topic

        #print(f"Received MQTT data for {topic}: {payload}")

        decoded_payload = payload.decode("utf-8")

        

        #print(f"Publishing data for {topic}: {decoded_payload}")


        if self._subtopic != None:

            #print(f"Subtopic: {self._subtopic}")
            try:
                json_payload = json.loads(payload)
                #print(f"JSON payload: {json_payload}")
                decoded_payload = json_payload[self._subtopic]
                #print(f"Decoded payload: {decoded_payload}")
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                return
        else:
            print("No subtopic")

        # Convert the payload to a string
        #if isinstance(payload, bytes):
            


        #self.publish(payload)
        _rtd_server.publish(self.topic(), decoded_payload) 

    def disconnect(self, num_subscribers: int):
        """
        Called when all subscribers have unsubscribed.
        """
        if num_subscribers == 0:
            self.stop()
            datahub.Unsubscribe(self._topic, self.on_message)
            return True

    def stop(self):
        """
        Stops the subscription.
        """
        print(f"Stopping subscription to {self._topic}")

        #_rtd_server.publish(self.topic(), "-")
        self._subscribed = False  # No explicit unsubscribe function in DataHub?

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

