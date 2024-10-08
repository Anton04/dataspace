

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
from IPython.display import Image, display
import imghdr

def payload_is_jpg(data):
    o = io.BytesIO(data)
    return imghdr.what(o) == "jpeg"

lastpayload = None

def default_handler(topic, payload, private):
    global lastpayload
    lastpayload = payload
    if payload_is_jpg(payload):
        display(Image(payload))
        return

    if private:
      print(topic + " (private)")
    else:
      print(topic + " (updated)")

    print("_" * len(topic))

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
