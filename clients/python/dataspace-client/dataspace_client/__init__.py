#NEW version
from __future__ import annotations
import paho.mqtt.client as mqtt
import json
import traceback
import time
import datetime
import pytz
import io
import threading
#import pandas as pd
import uuid
#from IPython.display import Image, display
import imghdr
from urllib.parse import urlparse
from ast import Pass
#from pythreejs import *
#from IPython.display import display
#import numpy as np
#import trimesh
import base64
#import ipywidgets as widgets
#from IPython.display import display, HTML
import uuid
from jsonpath_ng import parse as jsonpath_parse
from enum import Enum


__all__ = ["DataHub", "datahub", "__version__"]
__version__ = "0.1.3.15"

#Enum that describes 3 states 0 public, 1 private, 2 cached data
class message_type(Enum):
    PUBLIC = 0
    PRIVATE = 1
    RETAINED = 2
    CACHED = 3
    PENDING_UPDATE = 4

    def __str__(self):
        return self.name



def is_notebook() -> bool:
    return is_colab() or is_jupyter_notebook()

def is_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False

def is_jupyter_notebook():
    try:
        from IPython import get_ipython
        return "zmqshell" in str(type(get_ipython()))
    except:
        return False



_is_notebook = is_notebook()

if  _is_notebook:
    from IPython.display import Image, display, clear_output, HTML
    import ipywidgets as widgets


def payload_is_jpg(data):
    o = io.BytesIO(data)
    return imghdr.what(o) == "jpeg"

lastpayload = None

def default_handler(topic, payload, msg_type: message_type):
    global lastpayload
    global scene

    # Save last payload
    lastpayload = payload

    # ---------------------------------------------------------
    # 1. Detect payload type (Python object or binary)
    # ---------------------------------------------------------
    is_binary = isinstance(payload, (bytes, bytearray))
    is_python = not is_binary  # JSONPath results or retained JSON objects

    # ---------------------------------------------------------
    # 2. DIRECTORY LISTING (python or json)
    # ---------------------------------------------------------
    if topic.endswith('/'):
        # Case 1: payload is already a python object (list/dict)
        if is_python:
            entries = payload

        # Case 2: payload is binary JSON representing list/dict
        else:
            try:
                entries = json.loads(payload)
            except Exception:
                entries = None

        if isinstance(entries, (list, dict)):
            folder_emoji = "\U0001F4C1"
            file_emoji   = "\U0001F4C4"

            # If it's a dict we list only its keys
            if isinstance(entries, dict):
                entries = list(entries.keys())

            print(f"{topic} (directory{' ' + str(msg_type) if msg_type else ''})")
            print("_" * len(topic))

            for entry in entries:
                if isinstance(entry, str) and entry.endswith('/'):
                    print(f"{folder_emoji} {entry}")
                else:
                    print(f"{file_emoji} {entry}")
            return

    # ---------------------------------------------------------
    # 3. If Python object (JSONPath output) → pretty print
    # ---------------------------------------------------------
    if is_python:
        try:
            print(json.dumps(payload, indent=2))
        except:
            print(payload)
        return

    # ---------------------------------------------------------
    # 4. From here on: payload is binary (bytes)
    # ---------------------------------------------------------

    # JPG auto-preview
    if payload_is_jpg(payload):
        display(Image(payload))
        return

    # Print topic with private/public/cached tag
    print(topic + " " + str(msg_type) )
    print("_" * len(topic))

    # ---------------------------------------------------------
    # 5. GLB preview
    # ---------------------------------------------------------
    try:
        if topic.lower().endswith(".glb"):
            print("File size is: " + str(len(payload)))
            show_3d_model(payload)
            return
    except Exception:
        traceback.print_exc()

    # ---------------------------------------------------------
    # 6. Try to pretty-print JSON
    # ---------------------------------------------------------
    try:
        data = json.loads(payload)
        print(json.dumps(data, indent=2))
        return
    except:
        pass

    # ---------------------------------------------------------
    # 7. Try to print as UTF-8 string
    # ---------------------------------------------------------
    try:
        print(payload.decode("utf-8"))
        return
    except:
        pass

    # ---------------------------------------------------------
    # 8. Fallback: raw bytes
    # ---------------------------------------------------------
    print(payload)
    return





def show_3d_model(glb_data):
    # Generate a unique ID for the container to avoid conflicts
    unique_id = f"container_{uuid.uuid4().hex}"

    # Convert the binary data to a base64 encoded string for embedding in HTML
    glb_data_base64 = base64.b64encode(glb_data).decode('utf-8')

    # Create a small HTML and JavaScript snippet that loads the GLB data with lighting and orbit controls
    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>3D Model Viewer</title>
        <style>
            body {{ margin: 0; }}
            canvas {{ display: block; }}
            #{unique_id} {{
                width: 400px;  /* Set width of the container */
                height: 300px; /* Set height of the container */
                margin: auto;  /* Center the container */
            }}
        </style>
    </head>
    <body>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>

        <div id="{unique_id}"></div>
        <script>
            var container = document.getElementById('{unique_id}');
            var scene = new THREE.Scene();
            var camera = new THREE.PerspectiveCamera(75, 400 / 300, 0.1, 1000);  // Adjust camera aspect ratio
            var renderer = new THREE.WebGLRenderer();
            renderer.setSize(400, 300);  // Set the renderer size to match the container
            container.appendChild(renderer.domElement);

            // Add lighting to the scene
            var ambientLight = new THREE.AmbientLight(0xffffff, 1.0); // Soft white light
            scene.add(ambientLight);

            var directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
            directionalLight.position.set(5, 10, 7.5).normalize();
            scene.add(directionalLight);

            // Orbit controls for interaction (rotate, zoom, pan)
            var controls = new THREE.OrbitControls(camera, renderer.domElement);

            // Convert base64 data to a Blob and load it
            var binaryData = atob('{glb_data_base64}');
            var arrayBuffer = new Uint8Array(new ArrayBuffer(binaryData.length));
            for (var i = 0; i < binaryData.length; i++) {{
                arrayBuffer[i] = binaryData.charCodeAt(i);
            }}
            var blob = new Blob([arrayBuffer], {{type: 'model/gltf-binary'}});

            var loader = new THREE.GLTFLoader();
            loader.load(URL.createObjectURL(blob), function (gltf) {{
                scene.add(gltf.scene);
                camera.position.z = 5;
                controls.update();  // Make sure controls are updated when the model is loaded
                animate();
            }}, undefined, function (error) {{
                console.error(error);
            }});

            // Animation loop
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();  // Update controls for each frame
                renderer.render(scene, camera);
            }}
        </script>
    </body>
    </html>
    """

    # Create an Output widget
    out = widgets.Output()

    # Display the Output widget in the current cell
    display(out)

    # Clear the previous output and render the new HTML within the output widget
    with out:
        out.clear_output(wait=True)
        display(HTML(html_code))



class GetObject():
    def __init__(self, topic, handler=None):
        self.event = threading.Event()
        self.topic = topic
        self.payload = None
        self.handler = handler or self.update
        self.msg_type = None

    def update(self, topic, payload, msg_type: message_type):
        self.payload = payload
        self.msg_type = msg_type
        self.event.set()

class Broker:
    def __init__(self, broker, port, user, passw, basepath):

        print("Connecting as: " + str(user) + "@" + broker + ":" + str(port))

        self.client_id = f'client-{uuid.uuid4()}'
        self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv5)  # Use the latest MQTT version

        self.basepath = basepath
        self.default_timezone = pytz.timezone('Europe/Stockholm')
        self.cache = True
        self.cached = {}
        self.cached_ts = {}
        self.cached_msg_type = {}

        self.debug_msg = []
        self.debug = False
        self.lasttopic = ""

        self.subscriptions = {}
        self.gets = []

        # An update is an operation that will update a jsonpath as soon as we have full json. 
        self.pending_updates = {}   # topic_root → [UpdateOperation, ...]


        self.broker = broker
        self.port = port

        # Bind callbacks
        self.client.username_pw_set(username=user, password=passw)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Connect to broker
        self.client.connect(broker, port, 60)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"Connected with result code {rc}")
        for topic in self.subscriptions.keys():
            self.client.subscribe(topic)

    class UpdateOperation:
        def __init__(self, broker, topic_root, jsonpath, new_value, timeout=10):
            self.broker = broker
            self.topic_root = topic_root
            self.jsonpath = jsonpath
            self.new_value = new_value
            self.deadline = time.time() + timeout

        def handler(self, full_topic, payload, msg_type: message_type):
            # Only act on the correct topic
            #if full_topic != self.topic_root:
            #    return

            # Timeout?
            if time.time() > self.deadline:
                self.cleanup()
                return
            
            #Check if payload is null
            if payload is None:
                base = {}
            else:
                #Check if payload is already a python object else parse json
                try:

                    if not isinstance(payload, (dict, list)):
                        base = json.loads(payload)
                    else:
                        base = payload


                except Exception:
                    self.cleanup()
                    print("JSON update operation failed: could not parse existing data: " + str(payload))
                    return

            # Apply JSONPath update
            try:
                expr = jsonpath_parse(self.jsonpath)
                expr.update(base, self.new_value)
            except Exception:
                # Silently ignore JSONPath problems
                self.cleanup()
                return

            # Publish full updated JSON back to topic
            new_json = json.dumps(base).encode("utf-8")
            self.broker.client.publish(self.topic_root, new_json, qos=0, retain=False)
            self.broker.cache_payload(self.topic_root, new_json, msg_type=message_type.PENDING_UPDATE)

            # After successful update → clean up
            self.cleanup()

        def cleanup(self):
            # Remove from pending list
            ops = self.broker.pending_updates.get(self.topic_root, [])
            if self in ops:
                ops.remove(self)
            if not ops:
                self.broker.pending_updates.pop(self.topic_root, None)

            # Unsubscribe the temporary handler
            try:
                self.broker.Unsubscribe(self.topic_root, self.handler)
            except:
                pass


    def Publish(self, topic, payload=None, qos=0, retain=False, properties=None, timeout=2):
        # Split into topic + optional JSONPath
        topic_root, jsonpath = self.parse_topic_jsonpath(topic)

        # CASE 1: normal publish → no JSONPath
        if not jsonpath:

            #Check if payload is text or binary otherwise convert to utf-8 if it is object to json.dumps

            if not isinstance(payload, (str, bytes, bytearray)):
                payload = json.dumps(payload).encode("utf-8")

            self.client.publish(topic_root, payload, qos, retain, properties)
            self.cache_payload(topic_root, payload, msg_type=message_type.PENDING_UPDATE)
            return

        # CASE 2: JSONPath update request (NON-BLOCKING)

        # Decode incoming payload → new_value
        try:
            if isinstance(payload, (bytes, bytearray)):
                new_value = json.loads(payload)
            else:
                new_value = payload
        except Exception:
            if isinstance(payload, (bytes, bytearray)):
                new_value = payload.decode("utf-8", errors="ignore")
            else:
                new_value = payload

        # Create update operation
        op = self.UpdateOperation(self, topic_root, jsonpath, new_value, timeout)

        # Store operation
        if topic_root not in self.pending_updates:
            self.pending_updates[topic_root] = []
        self.pending_updates[topic_root].append(op)

        # Subscribe temporary handler
        # It will fire *on the next message*, or cached value
        self.Subscribe(topic_root, op.handler)



    def parse_topic_jsonpath(self,url_path: str):
        idx = url_path.rfind('$')

        if idx == 0:
            # Hela strängen är topic
            return url_path, None

        if idx <= 0:
            # Ingen JSONPath → hela strängen är URL-sökvägen
            return url_path, None

        url = url_path[:idx]     # t.ex. "$private/test"
        jsonpath = url_path[idx:]       # t.ex. "$object1.name"

        return url, jsonpath


    def ApplyJsonPath(self, payload, jsonpath):
        # 1. Ingen JSONPath → returnera hela payload
        if not jsonpath:
            return payload
        

        try:
            json_payload = json.loads(payload)
        except Exception as e:
            # Payload är inte giltig JSON → returnera None
            return payload

        try:
            # 2. Kompilera JSONPath
            expr = jsonpath_parse(jsonpath)

            # 3. Utför matchning
            matches = expr.find(json_payload)

            # 4. Ingen träff → returnera None
            if not matches:
                return None

            # 5. Om det bara finns en träff → returnera värdet
            if len(matches) == 1:
                return matches[0].value

            # 6. Flera träffar → returnera en lista av värden
            return [m.value for m in matches]

        except Exception as e:
            # JSONPath-fel → returnera None
            return None

    def Subscribe(self, topic, handler=default_handler):

        topic, jsonpath = self.parse_topic_jsonpath(topic)

        if topic in self.subscriptions.keys():
            if (handler, jsonpath) not in self.subscriptions[topic]:
                self.subscriptions[topic].append((handler, jsonpath))
                cached_payload = self.get_cached(topic)
                if cached_payload and callable(handler):
                    prefix = "mqtt://"
                    payload = self.ApplyJsonPath(cached_payload, jsonpath)
                    handler(prefix + self.broker + "/" + topic, payload, message_type.CACHED)
        else:
            self.subscriptions[topic] = [(handler, jsonpath)]
            self.client.subscribe(topic)
            self.client.subscribe(f"$private/{self.client_id}/{topic}")

    #If there is a cached message for the topic return it
    def get_cached(self, topic):
        if topic in self.cached.keys():
            return self.cached[topic]
        return None


    def Get(self, topic, blocking=True, handler=default_handler, timeout=10):
        get_obj = GetObject(topic, handler)
        self.gets.append((topic, get_obj))

        self.Subscribe(topic,get_obj.update)

        if blocking:
            if not get_obj.event.wait(timeout=timeout):
                print("Timeout")
                self.Unsubscribe(topic, get_obj.update)

            if handler is None:
                return get_obj.payload
            elif callable(get_obj.handler):
                prefix = "mqtt://"
                return get_obj.handler(prefix + self.broker + "/" + topic, get_obj.payload,get_obj.msg_type)

        return None

    def GetDataFrame(self, topic, timeout=10):
        import pandas as pd
        data = self.Get(topic, blocking=True, handler=None, timeout=timeout)
        df = pd.read_json(data.decode("utf-8"), lines=True, orient="records")
        df.index = pd.to_datetime(df["time"], unit="s")
        return df

    def GetDataFrameAt(self, topic, ts, timeout=10):
        data = self.Get(self.GetTimeIndexPath(topic, ts), blocking=True, handler=None, timeout=10)
        df = pd.read_json(data.decode("utf-8"), lines=True, orient="records")
        df.index = pd.to_datetime(df["time"], unit="s")
        return df

    def Unsubscribe(self, topic, handler=default_handler):
        topic, jsonpath = self.parse_topic_jsonpath(topic)

        if topic not in self.subscriptions:
            return
        if (handler, jsonpath) not in self.subscriptions[topic]:
            return
        self.subscriptions[topic].remove((handler, jsonpath))
        if len(self.subscriptions[topic]) == 0:
            self.client.unsubscribe(topic)
            self.client.unsubscribe(f"$private/{self.client_id}/{topic}")
            del self.subscriptions[topic]


    def cache_payload(self, topic, payload,msg_type: message_type = message_type.PUBLIC):
        if self.cache:
            self.cached[topic] = payload
            self.cached_ts[topic] = int(time.time())
            self.cached_msg_type[topic] = msg_type

    def on_message(self, client, userdata, msg):
        try:
            if self.debug:
                print(f"{int(time.time())} Update received: {msg.topic}")
                self.debug_msg.append(f"{int(time.time())} Update received: {msg.topic}")
                self.debug_msg = self.debug_msg[-10:]

            

            to_be_unsubscribed = []

            if msg.topic.find(f"$private/{self.client_id}/") == 0:
                topic = msg.topic[len(f"$private/{self.client_id}/"):]
                msg_type = message_type.PRIVATE
            else:
                topic = msg.topic

                if msg.retain == 1:
                   msg_type = message_type.RETAINED
                else:               
                    msg_type = message_type.PUBLIC

            self.cache_payload(topic, msg.payload,msg_type=msg_type)

            if topic in self.subscriptions:
                for (handler, jsonpath) in self.subscriptions[topic]:

                    msg_payload = self.ApplyJsonPath(msg.payload, jsonpath)

                    if callable(handler):
                        prefix = "mqtt://"
                        handler(prefix + self.broker + "/" + topic, msg_payload,msg_type)

                    if (topic, handler) in self.gets:
                        to_be_unsubscribed.append((topic, handler))

            for topic, handler in to_be_unsubscribed:
                self.gets.remove((topic, handler))
                self.Unsubscribe(topic, handler)

            self.lasttopic = msg.topic
        except:
            traceback.print_exc()

    def find(self,name,handler=default_handler,basepath = None):
        if basepath ==None:
            basepath = self.basepath + "/"
        #print(basepath + "?find=\"" + name +"\"")
        self.Get(basepath + "?find=\"" + name +"\"",handler)

    def ls(self,topic,handler=default_handler):
        self.Get(topic + "/",handler)

    def GetLogAt(self,topic,epoc_time,handler=default_handler):

        self.Get(self.GetTimeIndexPath(topic,epoc_time),handler)

    def GetFilesAt(self,topic,epoc_time,handler=default_handler):

        self.Get(self.GetTimeIndexPath(topic,epoc_time)+ "/",handler)

    def GetTimeIndexPathFromDataTime(self,topic,localtime):
        return topic + "/TimeIndex/" + str(localtime.year) + "/" +  str(localtime.month).zfill(2) + "/" + str(localtime.day).zfill(2) + "/" + str(localtime.hour).zfill(2)

    def GetTimeIndexPath(self,topic,epoc_time):
        date_time = datetime.datetime.fromtimestamp( epoc_time )
        localtime = date_time.astimezone(self.default_timezone)
        return self.GetTimeIndexPathFromDataTime(topic,localtime)








# DataHub implementation



class DataHub:
    def __init__(self):

        # Credentials are stored as {"serveradress":{"user":"username","password":"mypassword"}}
        self.credentials = {}

        # Servers are stored as {"serveradress":Broker object}
        self.servers = {}

        self.debug = False

    def add_credentials(self, server, username, password):

        """Store credentials for a server. There is no connection make until a get, subscribe or publish is done.

        Args:
            server_url: Full URL like "mqtt://host[:port]" or "mqtts://host[:port]".
            user:       Username.
            password:   Password (stored in-memory for this process).

        Notes:
            The internal key is normalized to host[:port] without scheme.
        """

        #Remove mqtt:// if it server starts with it
        if server.find("mqtt://") == 0:
          server = server[len("mqtt://"):]

        self.credentials[server] = {"user": username, "password": password}

    def delete_credentials(self, server):
        """Delete stored credentials for a server.

        Args:
            server_url: Full URL like "mqtt://host[:port]" or "mqtts://host[:port]".
        """

        #Remove mqtt:// if it server starts with it
        if server.find("mqtt://") == 0:
          server = server[len("mqtt://"):]

        if server in self.credentials:
            del self.credentials[server]

        #Check if server exists in servers and remove it
        if server in self.servers:
            del self.servers[server]
    

    #Take any adress and see if credentials exists for it return true/false
    def get_credentials(self, url: str):

        #Extract server adress from url
        parsed_url = urlparse(url)
        server_address = parsed_url.hostname
        return self.credentials.get(server_address) != None

    def login(self, server: str, user: str,
              password: str | None = None, *, prompt_password: bool = True):
        """Prompt for a password (if not given) and register credentials.

        Args:
            server: Host or full URL (e.g. "iot.example.com" or "mqtts://iot.example.com:8883").
            user:   Username to authenticate with.
            password: Optional password. If omitted and `prompt_password=True`,
                      a hidden prompt will be shown (falls back to visible input if needed).
            prompt_password: Whether to prompt when `password` is None.

        Returns:
            DataHub: The same instance (allows chaining).

        Examples:
            >>> from dataspace_client import datahub
            >>> datahub.login("iot.example.com", "alice")   # prompts for password
            <dataspace_client.DataHub ...>
        """
        if password is None and prompt_password:
            try:
                import getpass  # lazy import: only when needed
                password = getpass.getpass(f"Password for {user}@{server}: ")
            except Exception:
                # Fallback for environments without a controllable TTY (some notebooks)
                password = input(f"Password for {user}@{server}: ")

        server_url = server if server.startswith(("mqtt://", "mqtts://")) else f"mqtt://{server}"
        self.add_credentials(server_url, user, password)
        return self

    def add_server(self, server_adress):

        if not server_adress or len(server_adress) == 0:
            self.DebugPrint("No server adress given",True)
            return None

        if server_adress in self.servers:
            self.DebugPrint(f"Server {server_adress} already exists")
            return self.servers[server_adress]

        server_adress_wo_scheme = server_adress
        if server_adress.find("mqtt://") == 0:
            server_adress_wo_scheme = server_adress[len("mqtt://"):]
        elif server_adress.find("mqtts://") == 0:
            server_adress_wo_scheme = server_adress[len("mqtts://"):]
        #In case of websocket, remove ws:// or wss://
        elif server_adress.find("ws://") == 0:
            server_adress_wo_scheme = server_adress[len("ws://"):]
        elif server_adress.find("wss://") == 0:
            server_adress_wo_scheme = server_adress[len("wss://"):]

        credentials = self.credentials.get(server_adress_wo_scheme)
        if not credentials:
            self.DebugPrint(f"No credentials found for server: {server_adress}")
            credentials = {"user": None, "password": None}

        server = Broker(broker=server_adress,port=1883,user=credentials["user"],passw=credentials["password"],basepath="datadirectory")
        server.debug = self.debug

        self.DebugPrint(f"Server {server_adress} added")

        self.servers[server_adress] = server

        return server


    def SplitPath(self,url):

         # Parse the URL
        parsed_url = urlparse(url)

        # Extract components
        protocol = parsed_url.scheme
        server_adress = parsed_url.hostname
        path = parsed_url.path
        port = parsed_url.port
        query = parsed_url.query
        fragment = parsed_url.fragment

        #Remove leading slash
        if len(path) > 1 and path[0] == "/":
            path = path[1:]

        return server_adress,path

    def Subscribe(self,url,callback=default_handler):

        server_adress,path = self.SplitPath(url)

        server = self.add_server(server_adress)

        self.DebugPrint("Subscribing to: " + path)

        server.Subscribe(path,callback)


    def Unsubscribe(self,url,callback=default_handler):

        self.DebugPrint("Unsubscribing from: " + url)

        server_adress,path = self.SplitPath(url)

        server = self.add_server(server_adress)

        if server_adress not in self.servers:
            self.DebugPrint(f"Server {server_adress} does not exist")
            return

        server = self.servers[server_adress]

        server.Unsubscribe(path,callback)

        self.DebugPrint("Unsubscribed from: " + path)

    def Get(self, url, blocking=True, handler=default_handler, timeout=10):

        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        if server == None:
            self.DebugPrint(f"Could not connect to {server_adress}")
            return

        return server.Get(topic, blocking=blocking, handler=handler, timeout=timeout)
    

    def add_user_with_role(self, server_url,  
                       username, password, fullname=None,
                       create_user_dir=True):
        
        # If no protocol is given, assume mqtt:// 
        if server_url.find("mqtt://") != 0 and server_url.find("mqtts://") != 0 and server_url.find("ws://") != 0 and server_url.find("wss://") != 0:
            server_url = "mqtt://" + server_url
      
        server_adress,path = self.SplitPath(server_url)

        server = self.add_server(server_adress)

        dyn = DynSec(server)

        rolename = f"{username}_role"
        user_topic_pattern = f"datadirectory/Users/{username}/#"
        private_topic_pattern = f"$private/+/datadirectory/Users/{username}/#"
        name_topic = f"datadirectory/Users/{username}/name"

        # 1) role + ACLs
        dyn.create_role(rolename, textname=f"Role for {username}")
        for acl in [
            ("publishClientSend",    user_topic_pattern,    True, 1),
            ("publishClientReceive", user_topic_pattern,    True, 1),
            ("subscribePattern",     user_topic_pattern,    True, 1),
            ("subscribePattern",     private_topic_pattern, True, 1),
            ("publishClientReceive", private_topic_pattern, True, 1),
        ]:
            dyn.add_role_acl(rolename, acl[0], acl[1], allow=acl[2], priority=acl[3])

        # 2) client + bind role
        dyn.create_client(username, password, textname=fullname or username)
        dyn.add_client_role(username, rolename, priority=1)

        # 3) skriv namn i din datastruktur (non retained)
        if create_user_dir and fullname:
            payload = json.dumps({"default": fullname}).encode("utf-8")
            server.Publish(name_topic, payload, qos=1, retain=False)

        return True


    def GetFilesAt(self,url,epoc_time,handler=default_handler):

        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        if server == None:
            self.DebugPrint(f"Could not connect to {server_adress}")
            return

        server.GetFilesAt(topic, epoc_time,handler)

    def GetDataFrame(self, url, timeout=10):
        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        if server == None:
            self.DebugPrint(f"Could not connect to {server_adress}")
            return

        return server.GetDataFrame(topic, timeout)

    def GetDataFrameAt(self, url, ts, timeout=10):
        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        if server == None:
            self.DebugPrint(f"Could not connect to {server_adress}")
            return

        return server.GetDataFrameAt(topic,ts ,timeout)


    def Publish(self,url, payload=None, qos=0, retain=False, properties=None):

        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        self.DebugPrint("Publishing to: " + url)

        server.Publish(topic, payload, qos, retain, properties)

        


    def GetCache(self,url):
        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        self.DebugPrint("Getting cached from: " + url)

        return server.get_cached(topic)

    def Link(self,url, target):

        server_adress,topic = self.SplitPath(url)

        server = self.add_server(server_adress)

        self.DebugPrint("Publishing to: " + url)

        server.Publish(topic + "?link=" + target,"")


    def DebugPrint(self,message,force=False):
        if self.debug or force:
          print(message)





import json
import uuid
import threading

CONTROL_TOPIC  = "$CONTROL/dynamic-security/v1"
RESPONSE_TOPIC = "$CONTROL/dynamic-security/v1/response"

class DynSec:
    """
    Enkel dynsec-klient:
    - Persistent prenumeration på response-topic
    - Registrerar väntare (Event) innan publish
    - Matchar svar via correlationData och triggar Event
    """

    def __init__(self, broker):
        """
        broker: din Broker-instans (måste ha .client (Paho) och .Subscribe(topic, handler))
        """
        self.broker = broker
        self._waiters = {}  # corr_id -> threading.Event
        self._answers = {}  # corr_id -> response
        self._subscribed = False
        self._ensure_subscribed()

    # ---- intern: se till att vi lyssnar på responstopicen en gång ----
    def _ensure_subscribed(self):
        if not self._subscribed:
            self.broker.Subscribe(RESPONSE_TOPIC, self._on_response)
            self._subscribed = True  # idempotent nog; din Broker kan själv hantera dubbletter

    # ---- generell handler för alla dynsec-svar ----
    def _on_response(self, topic, payload, msg_type: message_type):
        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            return

        responses = data.get("responses", [])
        if not isinstance(responses, list):
            return

        for r in responses:
            corr = r.get("correlationData")
            if not corr:
                continue
            evt = self._waiters.get(corr)
            if evt is not None:
                # Viktigt: skriv svaret före vi signalerar eventet
                self._answers[corr] = r
                evt.set()
            else:
                # Ingen väntare registrerad för detta id (ignorera/logga vid behov)
                pass

    # ---- low-level: skicka kommando och vänta på svaret ----
    def _send(self, command: str, data: dict | None, timeout: float = 10.0) -> dict:
        corr = str(uuid.uuid4())
        cmd = {"command": command, "correlationData": corr}
        if data:
            cmd.update(data)
        payload = {"commands": [cmd]}

        # registrera väntaren FÖRE publish
        evt = threading.Event()
        self._waiters[corr] = evt

        # publicera (QoS 1) och vänta tills Paho skickat klart för att minska race
        info = self.broker.client.publish(
            CONTROL_TOPIC,
            json.dumps(payload).encode("utf-8"),
            qos=1,
            retain=False
        )
        info.wait_for_publish()

        # vänta på att handlern triggar vår Event
        ok = evt.wait(timeout)

        # plocka svaret och städa
        resp = self._answers.pop(corr, None)
        self._waiters.pop(corr, None)

        if not ok or resp is None:
            raise RuntimeError(f"dynsec timeout for {command}")

        # enkel fel/idempotens-hantering
        if resp.get("error"):
            msg = str(resp.get("errorMessage") or resp.get("error"))
            if "already" not in msg.lower():
                raise RuntimeError(f"dynsec error for {command}: {msg}")
        return resp

    # ---- publika operationer ----
    def create_role(self, rolename, textname=None):
        data = {"rolename": rolename}
        if textname:
            data["textname"] = textname
        return self._send("createRole", data)

    def add_role_acl(self, rolename, acltype, topic, allow=True, priority=1):
        return self._send("addRoleACL", {
            "rolename": rolename,
            "acltype": acltype,
            "topic": topic,
            "allow": allow,
            "priority": priority
        })

    def create_client(self, username, password, textname=None):
        data = {"username": username, "password": password}
        if textname:
            data["textname"] = textname
        return self._send("createClient", data)

    def add_client_role(self, username, rolename, priority=1):
        return self._send("addClientRole", {
            "username": username,
            "rolename": rolename,
            "priority": priority
        })
    
    # ---------- NEW: group ops ----------
    def create_group(self, groupname: str):
        return self._send("createGroup", {"groupname": groupname})

    def add_group_client(self, groupname: str, username: str):
        return self._send("addGroupClient", {"groupname": groupname, "username": username})

    def add_group_role(self, groupname: str, rolename: str, priority: int = 1):
        return self._send("addGroupRole", {"groupname": groupname, "rolename": rolename, "priority": priority})

    def ensure_group_permissions(self, groupname: str) -> dict:
        """
        Ensure a role for the group exists with R/W perms on the group's dataspace, and attach it to the group.
        ACLs mirror your user-space defaults but for the group-space.
        """
        role = f"group_{groupname}_role"

        # 1) create role (idempotent)
        try:
            self.create_role(role, textname=f"Role for group {groupname}")
        except RuntimeError as e:
            # ignore "already exists"
            if "already" not in str(e).lower():
                raise

        # 2) add ACLs on group dataspace
        group_topic = f"datadirectory/Groups/{groupname}/#"
        private_pat = f"$private/+/{group_topic}"

        acls = [
            ("publishClientSend",    group_topic, True, 1),
            ("publishClientReceive", group_topic, True, 1),
            ("subscribePattern",     group_topic, True, 1),
            ("subscribePattern",     private_pat, True, 1),
            ("publishClientReceive", private_pat, True, 1),
        ]
        for acltype, topic, allow, prio in acls:
            try:
                self.add_role_acl(role, acltype, topic, allow=allow, priority=prio)
            except RuntimeError as e:
                if "already" not in str(e).lower():
                    raise

        # 3) attach role to group (idempotent)
        try:
            self.add_group_role(groupname, role, priority=1)
        except RuntimeError as e:
            if "already" not in str(e).lower():
                raise

        return {"group": groupname, "role": role, "acls": len(acls)}



# Skapa global instans vid import (ingen lazy)
datahub = DataHub()


