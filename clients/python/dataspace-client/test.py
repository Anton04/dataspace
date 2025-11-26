# DataHub Tutorial Script (Följer tutorialen exakt)
# Kör: python datahub_tutorial_full.py

from dataspace_client import datahub
import time
import json

def pause(msg="\nTryck ENTER för att fortsätta..."):
    input(msg)

print("=== DIGIVIS DataHub Tutorial ===")
pause()

# ------------------------------------------------------------
# 1. LOGIN
# ------------------------------------------------------------
print("Steg 1: Loggar in...")
user = input("Enter username: ")
hub = datahub.login("iot.digivis.se", user)
print("Inloggad på iot.digivis.se som " + user)
pause()

# ------------------------------------------------------------
# 2. SUBSCRIBE utan callback
# ------------------------------------------------------------
TOPIC = "mqtt://iot.digivis.se/datadirectory/TestArea/signalA"

print(f"Steg 2: Subscribar till {TOPIC} utan callback...")
datahub.Subscribe(TOPIC)
time.sleep(5)
print("\nUnsubscribar...")
datahub.Unsubscribe(TOPIC)
pause()

# ------------------------------------------------------------
# 3. SUBSCRIBE med egen callback
# ------------------------------------------------------------
print("Steg 3: Subscribar med egen callback...")

def myfunc(topic, data, private):
    print(f"Callback → topic: {topic}")

print(f"Subscribar till {TOPIC} med 'myfunc'...")
datahub.Subscribe(TOPIC, myfunc)
time.sleep(5)
print("\nUnsubscribar...")
datahub.Unsubscribe(TOPIC, myfunc)
pause()

# ------------------------------------------------------------
# 4. PUBLISH
# ------------------------------------------------------------
print("Steg 4: Publicerar data...")
payload = json.dumps({"test": 34})
print("Skickar {test:34} till TestArea/testdata...")
datahub.Publish("mqtt://iot.digivis.se/datadirectory/TestArea/testdata", payload)
pause()

# ------------------------------------------------------------
# 5. GET (blocking)
# ------------------------------------------------------------
print("Steg 5: GET-blocking av Readme.md...")
res = datahub.Get("mqtt://iot.digivis.se/datadirectory/Namespaces/Readme.md")
print("Resultat:\n", res)
pause()

# ------------------------------------------------------------
# 6. LISTA MAPP (GET med trailing slash)
# ------------------------------------------------------------
print("Steg 6: Listar innehållet i TestArea/...\n")
res = datahub.Get("mqtt://iot.digivis.se/datadirectory/TestArea/")
print(res)
pause()

# ------------------------------------------------------------
# 7. Läs tutorial-folder
# ------------------------------------------------------------
print("Steg 7: Listar tutorial-folder...")
res = datahub.Get("mqtt://iot.digivis.se/datadirectory/TestArea/tutorial/")
print(res)
pause()

# ------------------------------------------------------------
# 8. Publish ny fil till tutorial-folder
# ------------------------------------------------------------
print("Steg 8: Skapar en ny fil i tutorial-foldern...")

filename = "myfile4.md"   # ändra om du vill
payload = "this is file 4 that i made"

print(f"Publicerar {filename}...")
datahub.Publish(f"mqtt://iot.digivis.se/datadirectory/TestArea/tutorial/{filename}", payload)
pause()

print("=== TUTORIAL KLAR ===")
print("Du har nu följt hela DataHub-exemplet steg-för-steg.")


