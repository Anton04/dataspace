

#NEW version
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
    from IPython.display import Image, display, clear_output
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

        print("Connecting as: " + user + "@" + broker + ":" + str(port))

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

        #Remove mqtt:// if it server starts with it
        if server.find("mqtt://") == 0:
          server = server[len("mqtt://"):]

        self.credentials[server] = {"user": username, "password": password}

    def add_server(self, server_adress):

        if server_adress in self.servers:
            self.DebugPrint(f"Server {server_adress} already exists")
            return self.servers[server_adress]

        credentials = self.credentials.get(server_adress)
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


    def DebugPrint(self,message):
        if self.debug:
          print(message)
