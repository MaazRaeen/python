import cv2
import mediapipe as mp
import pygetwindow as gw
import os
import asyncio
import websockets

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)

# Ask for peer IP
peer_ip = input("Enter the peer's IP (receiver enters sender's, sender enters receiver's): ").strip()

def get_active_file():
    """ Get the active PDF file opened on the screen """
    try:
        window = gw.getActiveWindow()
        if window:
            if callable(window.title):
                title_text = window.title()
            else:
                title_text = str(window.title)
                
            if title_text:
                # Remove the "Preview " prefix if present
                if title_text.startswith("Preview "):
                    title_text = title_text[8:]  # Remove "Preview "
                
                # Also try with the original title in case the window title is accurate
                possible_titles = [title_text]
                
                # Check for common separators and get the first part
                for separator in [" - ", " – ", ": "]:
                    if separator in title_text:
                        possible_titles.append(title_text.split(separator)[0].strip())
                
                print(f"Looking for PDFs matching: {possible_titles}")
                downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
                
                # List all PDF files in downloads folder
                all_pdfs = [f for f in os.listdir(downloads_folder) if f.lower().endswith('.pdf')]
                print(f"Available PDFs: {all_pdfs}")
                
                # Try to find a match by checking if any title is a substring of any PDF file
                for pdf in all_pdfs:
                    pdf_lower = pdf.lower()
                    for title in possible_titles:
                        title_lower = title.lower()
                        if title_lower in pdf_lower or pdf_lower.startswith(title_lower.replace(" ", "-")):
                            return os.path.join(downloads_folder, pdf)
                
                print(f"No matching PDF found in {downloads_folder}")
            else:
                print("Could not get window title")
        else:
            print("No active window detected")
    except Exception as e:
        print(f"Error getting active file: {e}")
    
    # Fallback to manual selection
    return select_pdf_manually()

def select_pdf_manually():
    """ Let user select a PDF from Downloads folder """
    try:
        downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        pdf_files = [f for f in os.listdir(downloads_folder) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print("No PDF files found in Downloads folder")
            return None
            
        print("\nAvailable PDF files:")
        for i, file in enumerate(pdf_files, 1):
            print(f"{i}. {file}")
            
        selection = input("\nEnter the number of the file to send (or 'q' to cancel): ")
        if selection.lower() == 'q':
            return None
            
        try:
            index = int(selection) - 1
            if 0 <= index < len(pdf_files):
                selected_file = pdf_files[index]
                return os.path.join(downloads_folder, selected_file)
            else:
                print("Invalid selection number")
        except ValueError:
            print("Please enter a valid number")
            
    except Exception as e:
        print(f"Error listing PDF files: {e}")
    return None

def detect_gesture(image):
    """ Detects hand gestures for sending and receiving """
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)
    
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
            thumb_ip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_IP]
            index_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            pinky_tip = hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP]
            middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
            ring_tip = hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_TIP]
            index_mcp = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP]
            pinky_mcp = hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_MCP]
            
            # 👍 Thumbs-Up (Send)
            if thumb_tip.y < thumb_ip.y and index_tip.y > thumb_tip.y:
                return "send"
            
            # 👊 Fist (Receive) - All fingertips below their MCP joints
            if (index_tip.y > index_mcp.y and 
                middle_tip.y > index_mcp.y and 
                ring_tip.y > index_mcp.y and 
                pinky_tip.y > pinky_mcp.y):
                return "receive"
    return None

async def send_file():
    """ Sends the detected file to the receiver """
    file_path = get_active_file()
    if file_path and os.path.exists(file_path):
        print(f"📂 Sending file: {file_path}")
        try:
            async with websockets.connect(f"ws://{peer_ip}:5001", open_timeout=10) as websocket:
                filename = os.path.basename(file_path)
                await websocket.send(filename)  
                with open(file_path, "rb") as f:
                    await websocket.send(f.read())  
                print("✅ File sent successfully!")
        except Exception as e:
            print(f"❌ Error sending file: {e}")
    else:
        print("❌ No valid PDF found!")

async def receive_file(websocket):
    """ Receives a file from sender """
    try:
        filename = await websocket.recv()  
        file_data = await websocket.recv()  
        
        save_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
        with open(save_path, "wb") as f:
            f.write(file_data)
        
        print(f"✅ File received: {save_path}")
    except Exception as e:
        print(f"❌ Error receiving file: {e}")

async def start_receiver():
    """ Starts the WebSocket server to listen for incoming files """
    print("📡 Waiting for files on port 5001...")
    async with websockets.serve(receive_file, "0.0.0.0", 5001):  
        await asyncio.Future()

# Start camera for gesture detection
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    flipped_frame = cv2.flip(frame, 1)
    gesture = detect_gesture(flipped_frame)
    
    if gesture == "send":
        print("👍 Thumbs-Up detected! Sending file...")
        asyncio.run(send_file())
    
    elif gesture == "receive":
        print("👊 Fist detected! Starting receiver mode...")
        asyncio.run(start_receiver())
    
    cv2.imshow("Gesture Control", flipped_frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
