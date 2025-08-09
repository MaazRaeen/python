# airshare_node_autoport.py

import os
import cv2
import socket
import asyncio
import websockets
import mediapipe as mp
from random import randint

# ========== Pick Random Port ==========
def get_free_port():
    sock = socket.socket()
    sock.bind(('', 0))  # bind to any available port
    _, port = sock.getsockname()
    sock.close()
    return port

RECEIVE_PORT = get_free_port()

# ========== Ask for Peer IP and Port ==========
PEER_IP = input("🌐 Enter peer's IP address (e.g. 192.168.1.12): ").strip()
PEER_PORT = int(input("📨 Enter peer's receiver port (ask them): "))

ALLOWED_EXTENSIONS = {'.py', '.txt', '.cpp', '.java', '.js'}
RECEIVE_FOLDER = os.path.expanduser("~/Downloads/Received_Files")
os.makedirs(RECEIVE_FOLDER, exist_ok=True)

# ========== Gesture Setup ==========
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.8, min_tracking_confidence=0.8)

def detect_open_hand(image):
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)
    return bool(results.multi_hand_landmarks)

def get_latest_code_file(folder="."):
    files = [
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.isfile(f) and os.path.splitext(f)[1] in ALLOWED_EXTENSIONS
    ]
    if not files:
        return None
    return max(files, key=os.path.getmtime)

# ========== Receiver ==========
async def receive_files():
    async def handler(ws):
        filename = await ws.recv()
        data = await ws.recv()
        save_path = os.path.join(RECEIVE_FOLDER, filename)
        with open(save_path, 'wb') as f:
            f.write(data)
        print(f"\n📥 Received: {filename}")

    print(f"🟢 Receiver ready on ws://0.0.0.0:{RECEIVE_PORT}")
    async with websockets.serve(handler, "0.0.0.0", RECEIVE_PORT):
        await asyncio.Future()

# ========== Sender ==========
async def sender_loop():
    cap = cv2.VideoCapture(0)
    sent = False

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            continue

        if detect_open_hand(frame) and not sent:
            print("✋ Open hand gesture detected! Preparing to send...")
            file = get_latest_code_file()
            if file:
                await send_file(file)
                sent = True
                await asyncio.sleep(3)
                sent = False
            else:
                print("⚠️ No valid code file found to send.")

        cv2.imshow("Gesture Sender", frame)
        if cv2.waitKey(5) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

async def send_file(file_path):
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        data = f.read()

    uri = f"ws://{PEER_IP}:{PEER_PORT}"
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(filename)
            await ws.send(data)
            print(f"📤 Sent: {filename} to {uri}")
    except Exception as e:
        print(f"❌ Failed to send {filename}: {e}")

# ========== Main ==========
async def main():
    await asyncio.gather(
        receive_files(),
        sender_loop()
    )

if __name__ == "__main__":
    print(f"\n📡 Your receiving port is: {RECEIVE_PORT}")
    print("📨 Share this port number with the other device.\n")
    asyncio.run(main())