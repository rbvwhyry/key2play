import asyncio
import json
import websockets
from flask import Flask
from lib.functions import get_ip_address
from lib.log_setup import logger
import os

DIR_SONGS_DEFAULT = "Songs_Default/"  #bundled songs — tracked by git, can be updated
DIR_SONGS_USER = "Songs_User_Upload/"  #user uploads — gitignored
UPLOAD_FOLDER = DIR_SONGS_USER  #tells Flask where file.save() should write uploaded files

os.makedirs(DIR_SONGS_USER, exist_ok=True)  #create folder if missing; exist_ok means no crash if already there

webinterface = Flask(__name__, template_folder="templates")
webinterface.config["TEMPLATES_AUTO_RELOAD"] = True
webinterface.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
webinterface.config["MAX_CONTENT_LENGTH"] = 32 * 1000 * 1000
webinterface.json.sort_keys = False
webinterface.socket_input = []


def start_server(loop):
    async def learning(websocket):
        try:
            while True:
                await asyncio.sleep(0.01)
                for msg in webinterface.learning.socket_send[:]:
                    await websocket.send(str(msg))
                    webinterface.learning.socket_send.remove(msg)
        except Exception:
            pass

    async def ledemu_recv(websocket):
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg["cmd"] == "pause":
                    webinterface.ledemu_pause = True
                elif msg["cmd"] == "resume":
                    webinterface.ledemu_pause = False
            except websockets.exceptions.ConnectionClosed:
                pass
            except websockets.exceptions.WebSocketException:
                pass
            except Exception as e:
                logger.warning(e)
                return

    async def ledemu(websocket):
        try:
            await websocket.send(
                json.dumps(
                    {
                        "settings": {
                            "gamma": webinterface.ledstrip.led_gamma,
                            "reverse": webinterface.ledstrip.reverse,
                        }
                    }
                )
            )
        except Exception:
            pass
        while True:
            try:
                ledstrip = webinterface.ledstrip
                await asyncio.sleep(1 / ledstrip.WEBEMU_FPS)
                if webinterface.ledemu_pause:
                    continue
                await websocket.send(json.dumps({"leds": ledstrip.strip.getPixels()}))
            except websockets.exceptions.ConnectionClosed:
                pass
            except websockets.exceptions.WebSocketException:
                pass
            except Exception as e:
                logger.warning(e)
                return

    async def midi(websocket):
        """Zero-latency MIDI push via asyncio.Queue.
        msg_callback in midiports.py pushes events into ws_queue via call_soon_threadsafe;
        this handler awaits the queue — no polling, no sleep, no event loop starvation."""
        queue = asyncio.Queue() #per-connection queue; each connected client gets its own

        webinterface.midiports.ws_queue = queue #give midiports a reference so msg_callback can push into it
        webinterface.midiports.ws_loop = asyncio.get_event_loop() #give midiports the event loop for thread-safe puts

        try:
            while True:
                event = await queue.get() #blocks until a MIDI event arrives — zero CPU when idle

                batch = [event]

                while not queue.empty(): #drain any additional events that arrived simultaneously
                    batch.append(queue.get_nowait())

                await websocket.send(json.dumps(batch)) #push the batch immediately

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.warning(f"midi websocket error: {e}")
        finally:
            webinterface.midiports.ws_queue = None #clear the queue reference on disconnect so msg_callback stops pushing
            webinterface.midiports.ws_loop = None

    async def handler(websocket):
        if websocket.path == "/learning":
            await learning(websocket)
        elif websocket.path == "/ledemu":
            await asyncio.gather(ledemu(websocket), ledemu_recv(websocket))
        else:
            return  #no handler for this path — close connection

    async def main():
        logger.info("WebSocket listening on: " + str(get_ip_address()) + ":8765")
        async with websockets.serve(handler, "0.0.0.0", 8765):
            await asyncio.Future()

    webinterface.ledemu_pause = False
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


def stop_server(loop):
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.stop()

def start_midi_server(loop, midiports):
    async def midi(websocket):
        queue = asyncio.Queue()
        midiports.ws_queue = queue
        midiports.ws_loop = asyncio.get_event_loop()
        try:
            while True:
                event = await queue.get()
                batch = [event]
                while not queue.empty():
                    batch.append(queue.get_nowait())
                await websocket.send(json.dumps(batch))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.warning(f"midi websocket error: {e}")
        finally:
            midiports.ws_queue = None
            midiports.ws_loop = None

    async def main():
        logger.info("MIDI WebSocket listening on: " + str(get_ip_address()) + ":8766")
        async with websockets.serve(midi, "0.0.0.0", 8766):
            await asyncio.Future()

    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


def stop_midi_server(loop):
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.stop()


from webinterface import views, views_api, views_settings  # noqa: F401 E402

from webinterface import views, views_api, views_settings  # noqa: F401 E402
