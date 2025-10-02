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
import pandas as pd
import uuid
#from IPython.display import Image, display
import imghdr
from urllib.parse import urlparse
from ast import Pass
#from pythreejs import *
#from IPython.display import display
import numpy as np
import trimesh
import base64
#import ipywidgets as widgets
#from IPython.display import display, HTML
import uuid



__all__ = ["DataHub", "datahub", "__version__"]
__version__ = "0.1.3.15"






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

def default_handler(topic, payload, private):
    global lastpayload
    global scene
    lastpayload = payload
    if payload_is_jpg(payload):
        display(Image(payload))
        return

    if private:
      print(topic + " (private)")
    else:
      print(topic + " (public)")

    print("_" * len(topic))

    try:
      #Check if file has an glb ending
        if topic[-4:] == ".glb":

            #print("Is a GLB file!")

            print("File size is:" + str(len(payload)))

            show_3d_model(payload)

            #print("Showing scene")

            # Alternatively, you can display it in a browser interactively
            #scene.show(viewer='notebook')  # This will open the model in your browser

            return

        # Check if the topic has a trailing slash
        elif topic.endswith('/'):
            #print("Topic has a trailing slash.\nListing entries in payload:\n")

            # Folder and File Emojis using Unicode
            folder_emoji = "\U0001F4C1"  # Folder emoji
            file_emoji = "\U0001F4C4"    # File emoji

            # Load the payload which contains the JSON data
            entries = json.loads(payload)

            # Iterate through each entry in the payload
            for entry in entries:
                # Check if the entry has a trailing slash
                if entry.endswith('/'):
                    print(f"{folder_emoji} {entry}")  # Print folder emoji for entries with a trailing slash
                else:
                    print(f"{file_emoji} {entry}")  # Print file emoji for entries without a trailing slash

            return

    except Exception as e:
      # Print the traceback
      traceback.print_exc()


    try:
        data = json.loads(payload)
        print(json.dumps(data, indent=2))
        return
    except:
        pass

    try:
        print(payload.decode("utf-8"))
        return
    except:
        pass

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
        self.private = None

    def update(self, topic, payload,private):
        self.payload = payload
        self.private = private
        self.event.set()

class Broker:
    def __init__(self, broker, port, user, passw, basepath):

        print("Connecting as: " + str(user) + "@" + broker + ":" + str(port))

        self.client_id = f'client-{uuid.uuid4()}'
        self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv5)  # Use the latest MQTT version

        self.basepath = basepath
        self.default_timezone = pytz.timezone('Europe/Stockholm')
        self.retain = True
        self.retained = {}

        self.debug_msg = []
        self.debug = False
        self.lasttopic = ""

        self.subscriptions = {}
        self.gets = []

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


    def Publish(self,topic, payload=None, qos=0, retain=False, properties=None):
        self.client.publish(topic, payload, qos, retain, properties)

    def Subscribe(self, topic, handler=default_handler):
        if topic in self.subscriptions.keys():
            if handler not in self.subscriptions[topic]:
                self.subscriptions[topic].append(handler)
                if topic in self.retained.keys() and callable(handler):
                    handler(topic, self.retained[topic], True)
        else:
            self.subscriptions[topic] = [handler]

        self.client.subscribe(topic)
        self.client.subscribe(f"$private/{self.client_id}/{topic}")


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
                return get_obj.handler(topic, get_obj.payload,get_obj.private)

        return None

    def GetDataFrame(self, topic, timeout=10):
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
        if topic not in self.subscriptions:
            return
        if handler not in self.subscriptions[topic]:
            return
        self.subscriptions[topic].remove(handler)
        if len(self.subscriptions[topic]) == 0:
            self.client.unsubscribe(topic)
            self.client.unsubscribe(f"$private/{self.client_id}/{topic}")
            del self.subscriptions[topic]

    def on_message(self, client, userdata, msg):
        try:
            if self.debug:
                print(f"{int(time.time())} Update received: {msg.topic}")
                self.debug_msg.append(f"{int(time.time())} Update received: {msg.topic}")
                self.debug_msg = self.debug_msg[-10:]

            if self.retain:
                self.retained[msg.topic] = msg.payload

            to_be_unsubscribed = []

            if msg.topic.find(f"$private/{self.client_id}/") == 0:
               topic = msg.topic[len(f"$private/{self.client_id}/"):]
               private = True
            else:
               topic = msg.topic
               private = False

            if topic in self.subscriptions:
                for handler in self.subscriptions[topic]:
                    if callable(handler):
                        handler(topic, msg.payload,private)

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

        # 3) skriv namn i din datastruktur (retained)
        if create_user_dir and fullname:
            payload = json.dumps({"default": fullname}).encode("utf-8")
            server.Publish(name_topic, payload, qos=1, retain=True)

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
    def _on_response(self, topic, payload, private):
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


