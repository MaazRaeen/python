import cv2
import mediapipe as mp
import socket
import threading
import os
import time
import numpy as np

# MediaPipe Hands 
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7,
    max_num_hands=1
)

# Configuration
PORT = 5001
CHUNK_SIZE = 1024 * 1024
received_videos_folder = "received_videos"
os.makedirs(received_videos_folder, exist_ok=True)

# Global variables
receiving_mode = False
receive_thread = None
partner_ip = None
selected_video_path = None

def get_ip_address():
    """Get local IP address automatically"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def send_video():
    """Send the selected video file to partner"""
    global selected_video_path
    
    if not selected_video_path:
        print("❌ No video selected! Press 's' to choose a file")
        return
        
    if not os.path.exists(selected_video_path):
        print(f"❌ File not found: {selected_video_path}")
        return
        
    if not partner_ip:
        print("❌ Partner IP not configured!")
        return

    print(f"\n🚀 Sending: {os.path.basename(selected_video_path)}")
    print(f"📡 Receiver IP: {partner_ip}")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((partner_ip, PORT))
            
            # Send file size
            file_size = os.path.getsize(selected_video_path)
            s.sendall(str(file_size).encode())
            
            # Wait for ACK
            ack = s.recv(1024)
            if ack != b"ACK":
                raise ConnectionError("Receiver didn't acknowledge")
            
            # Send file in chunks
            bytes_sent = 0
            with open(selected_video_path, 'rb') as f:
                while bytes_sent < file_size:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    s.sendall(chunk)
                    bytes_sent += len(chunk)
                    print(f"📤 Sent {bytes_sent}/{file_size} bytes", end="\r")
            
            # Verify completion
            if s.recv(1024) == b"DONE":
                print("\n✅ Video sent successfully!")
            else:
                print("\n⚠️ Transfer incomplete")

    except socket.timeout:
        print("\n⌛ Connection timed out")
    except ConnectionRefusedError:
        print("\n❌ Connection refused. Is receiver running?")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

def start_receive_server():
    """Start listening for incoming files"""
    global receiving_mode
    
    def receive_server():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', PORT))
                s.settimeout(60)
                s.listen(1)
                
                print(f"\n📡 Ready to receive! Your IP: {get_ip_address()}")
                print("Waiting for connection...")
                
                conn, addr = s.accept()
                with conn:
                    # Get file size
                    file_size = int(conn.recv(1024).decode())
                    conn.sendall(b"ACK")
                    
                    # Receive file
                    received_bytes = 0
                    file_data = b""
                    while received_bytes < file_size:
                        chunk = conn.recv(CHUNK_SIZE)
                        if not chunk:
                            break
                        file_data += chunk
                        received_bytes += len(chunk)
                        print(f"📥 Received {received_bytes}/{file_size} bytes", end="\r")
                    
                    # Save file
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"received_{timestamp}.mp4"
                    save_path = os.path.join(received_videos_folder, filename)
                    
                    with open(save_path, 'wb') as f:
                        f.write(file_data)
                    
                    print(f"\n💾 Saved to: {save_path}")
                    conn.sendall(b"DONE")
                    
                    play_received_video(save_path)
                    
        except socket.timeout:
            print("\n⌛ Receive mode timed out (60s)")
        except Exception as e:
            print(f"\n❌ Receive error: {str(e)}")
        finally:
            receiving_mode = False
    
    receiving_mode = True
    threading.Thread(target=receive_server, daemon=True).start()

def play_received_video(video_path):
    """Play the received video"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        return
    
    print("\n▶️ Playing received video (Press 'q' to stop)")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        cv2.imshow('Received Video', frame)
        if cv2.waitKey(25) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

def detect_gestures():
    """Main gesture detection loop"""
    global partner_ip, selected_video_path, receiving_mode
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Could not open camera")
        return
    
    # Set partner IP
    print(f"\n🖥️  Your IP address: {get_ip_address()}")
    partner_ip = input("Enter partner's IP address: ").strip()
    
    print("\n👋 Gesture Controls:")
    print("👍 Thumbs Up - Send selected video")
    print("🖐️ Open Hand - Enter receive mode")
    print("Press 's' - Select video file")
    print("Press 'p' - Change partner IP")
    print("Press 'q' - Quit program")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Camera error")
            break
            
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)
        
        cv2.putText(frame, f"Partner: {partner_ip}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        if selected_video_path:
            cv2.putText(frame, f"Selected: {os.path.basename(selected_video_path)}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        if receiving_mode:
            cv2.putText(frame, "RECEIVE MODE ACTIVE", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        # Gesture detection
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                landmarks = hand_landmarks.landmark
                wrist = landmarks[mp_hands.HandLandmark.WRIST]
                
                # Thumb tip position (for thumbs up)
                thumb_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP]
                
                # Finger tips (for open hand)
                finger_tips = [
                    landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP],
                    landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP],
                    landmarks[mp_hands.HandLandmark.RING_FINGER_TIP],
                    landmarks[mp_hands.HandLandmark.PINKY_TIP]
                ]
                
                # Thumbs Up detection (send)
                if thumb_tip.y < wrist.y:  
                    cv2.putText(frame, "SEND", (50, 100), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    if selected_video_path and not receiving_mode:
                        print("\n👍 Thumbs up detected - Sending video!")
                        send_video()
                        time.sleep(2)  
                
                # Open Hand  (receive)
                fingers_extended = sum(1 for tip in finger_tips if tip.y < wrist.y)
                if fingers_extended >= 3:  
                    cv2.putText(frame, "RECEIVE", (50, 100), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    if not receiving_mode:
                        print("\n🖐️ Open hand detected - Starting receive mode!")
                        start_receive_server()
                        time.sleep(2)  

        cv2.imshow("Gesture Video Sender", frame)
        
        # Keyboard controls
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('p'):
            partner_ip = input("Enter new partner IP: ").strip()
            print(f"Partner IP updated to: {partner_ip}")
        elif key == ord('s'):  
            try:
                from AppKit import NSOpenPanel, NSOKButton
                panel = NSOpenPanel.openPanel()
                panel.setCanChooseFiles_(True)
                panel.setCanChooseDirectories_(False)
                panel.setAllowsMultipleSelection_(False)
                panel.setAllowedFileTypes_(["mp4", "mov", "avi"])
                
                if panel.runModal() == NSOKButton:
                    selected_video_path = panel.URLs()[0].path()
                    print(f"✅ Selected: {os.path.basename(selected_video_path)}")
            except ImportError:
                print("❌ Could not import AppKit. Using fallback method.")
                selected_video_path = input("Enter full path to video file: ").strip()

    cap.release()
    cv2.destroyAllWindows()
    print("\nProgram closed")

if __name__ == "__main__":
    print("=== Gesture Video Sender ===")
    print("1. Press 's' to select a video file")
    print("2. Use 👍 Thumbs Up to send")
    print("3. Use 🖐️ Open Hand to receive\n")
    detect_gestures()