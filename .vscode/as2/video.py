import cv2
import mediapipe as mp
import socket
import threading
import os
import time
import numpy as np

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)

video_path = "video.mp4"
PORT = 5001
receiving_mode = False
receive_thread = None
partner_ip = None  # Partner IP address

# Folder to store received videos
received_videos_folder = "received_videos"
if not os.path.exists(received_videos_folder):
    os.makedirs(received_videos_folder)

def get_ip_address():
    """Get the local IP address of the device."""
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except Exception as e:
        print(f"Error getting IP address: {e}")
        return "127.0.0.1"

def send_video():
    """Send video to the stored partner IP address."""
    global partner_ip
    
    try:
        if not os.path.exists(video_path):
            print("No video found to send!")
            return
            
        if not partner_ip:
            print("No partner IP address configured. Use 'p' key to configure.")
            return

        # Validate the video file
        file_size = os.path.getsize(video_path)
        print(f"File size: {file_size} bytes")
        if file_size < 1024:
            print("Error: Video file is too small or invalid.")
            return

        print(f"Sending video to {partner_ip}...")
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(10)  # Increased timeout
                    s.connect((partner_ip, PORT))
                    
                    # Send file size
                    s.sendall(str(file_size).encode())
                    
                    # Wait for ACK
                    ack = s.recv(1024)
                    if ack != b"ACK":
                        print("Receiver didn't acknowledge file size.")
                        continue  # Retry
                    
                    # Send file in chunks with progress tracking
                    with open(video_path, 'rb') as f:
                        bytes_sent = 0
                        while bytes_sent < file_size:
                            chunk = f.read(4096)  # Increased chunk size to 4KB
                            if not chunk:
                                break
                            s.sendall(chunk)
                            bytes_sent += len(chunk)
                            print(f"Sent {bytes_sent}/{file_size} bytes ({bytes_sent/file_size*100:.2f}%)")
                    
                    # Final ACK to confirm completion
                    final_ack = s.recv(1024)
                    if final_ack == b"DONE":
                        print("✅ Video sent successfully!")
                        return
                    else:
                        print("❌ Transfer incomplete. Receiver didn't confirm.")
                    
            except (ConnectionRefusedError, socket.timeout) as e:
                print(f"Connection error: {e}. Retrying...")
                time.sleep(retry_delay)
            except Exception as e:
                print(f"Error: {e}")
                break  # Stop retrying on non-recoverable errors
                
    except Exception as e:
        print(f"Fatal error: {e}")

def start_receive_server():
    """Start the receive server in a separate thread."""
    global receiving_mode
    receiving_mode = True
    
    def receive_server():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', PORT))
                s.settimeout(60)
                s.listen(1)
                print(f"\n📱 Ready to receive! Your IP: {get_ip_address()}")
                
                conn, addr = s.accept()
                with conn:
                    print(f"\nReceiving from {addr[0]}")
                    
                    # Get file size
                    file_size = int(conn.recv(1024).decode())
                    print(f"Receiving {file_size} bytes")
                    conn.sendall(b"ACK")  # Acknowledge
                    
                    # Receive file
                    received_data = b""
                    while len(received_data) < file_size:
                        chunk = conn.recv(4096)  # Match sender's chunk size
                        if not chunk:
                            break
                        received_data += chunk
                        progress = len(received_data)/file_size*100
                        print(f"Received {len(received_data)}/{file_size} bytes ({progress:.2f}%)")
                    
                    # Save the file
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    received_file = os.path.join("received_videos", f"video_{timestamp}.mp4")
                    with open(received_file, 'wb') as f:
                        f.write(received_data)
                    print(f"✅ Saved to: {received_file}")
                    
                    # Confirm completion
                    conn.sendall(b"DONE")
                    
                    # Play video
                    cap = cv2.VideoCapture(received_file)
                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break
                        cv2.imshow('Received Video', frame)
                        if cv2.waitKey(25) & 0xFF == ord('q'):
                            break
                    cap.release()
                    cv2.destroyAllWindows()
                    
        except socket.timeout:
            print("⌛ Receive mode timed out.")
        except Exception as e:
            print(f"❌ Receive error: {e}")
        finally:
            receiving_mode = False
    
    return threading.Thread(target=receive_server, daemon=True)

def configure_partner_ip():
    """Configure the partner's IP address."""
    global partner_ip
    partner_ip = input("\n🔄 Enter your partner's IP address: ")
    print(f"Partner IP set to: {partner_ip}")
    return partner_ip    

def detect_gestures():
    """Detects hand gestures for video recording and transfer."""
    global receive_thread, receiving_mode, partner_ip
    
    # Try different camera indices
    for camera_index in [0, 1, -1]:
        try:
            print(f"Trying to open camera {camera_index}")
            cap = cv2.VideoCapture(camera_index)
            
            if not cap.isOpened():
                print(f"Failed to open camera {camera_index}")
                continue
                
            print(f"Successfully opened camera {camera_index}")
            break
        except Exception as e:
            print(f"Error opening camera {camera_index}: {e}")
            continue
    else:
        print("Error: Could not open any camera")
        return

    # Configure partner IP at startup
    print(f"\n📱 Your IP address is: {get_ip_address()}")
    partner_ip = configure_partner_ip()

    video_recording = False
    video_writer = None
    last_action_time = 0  # Track the last time recording was started/stopped
    cooldown = 5  # 5-second cooldown
    
    print("\n👋 Gesture Controls:")
    print("✌  Two Fingers to start/stop video recording (5-second cooldown)")
    print("👊  Closed Fist to send video to pre-configured IP")
    print("🤚  Open Palm to enter receive mode (60 second timeout)")
    print("Press 'p' to change partner IP address")
    print("Press 'q' to quit\n")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Couldn't read frame from camera")
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            try:
                result = hands.process(rgb_frame)
            except Exception as e:
                print(f"Error processing frame: {e}")
                continue

            if result.multi_hand_landmarks:
                for hand_landmarks in result.multi_hand_landmarks:
                    try:
                        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        
                        landmarks = hand_landmarks.landmark
                        thumb_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP].y
                        index_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y
                        middle_tip = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y
                        ring_tip = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP].y
                        pinky_tip = landmarks[mp_hands.HandLandmark.PINKY_TIP].y

                        # Gesture: Two Fingers (Start/Stop Video Recording)
                        if (index_tip < thumb_tip and middle_tip < thumb_tip and
                            ring_tip > thumb_tip and pinky_tip > thumb_tip):
                            current_time = time.time()
                            if current_time - last_action_time >= cooldown:
                                if not video_recording:
                                    # Initialize VideoWriter
                                    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                    video_writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'mp4v'), 20.0, (frame_width, frame_height))
                                    video_recording = True
                                    last_action_time = current_time
                                    print("\n🎥 Started video recording!")
                                else:
                                    video_writer.release()
                                    video_recording = False
                                    last_action_time = current_time
                                    print("\n🎥 Stopped video recording!")
                        
                        # Gesture: Closed Fist (Send Video)
                        elif (index_tip > thumb_tip and middle_tip > thumb_tip and
                              ring_tip > thumb_tip and pinky_tip > thumb_tip and not video_recording and os.path.exists(video_path)):
                            send_video()
                        
                        # Gesture: Open Palm (Receive Video)
                        elif (index_tip < thumb_tip and middle_tip < thumb_tip and
                              ring_tip < thumb_tip and pinky_tip < thumb_tip and not receiving_mode):
                            receive_thread = start_receive_server()
                            receive_thread.start()
                            
                    except Exception as e:
                        print(f"Error processing hand landmarks: {e}")
                        continue

            # Write frame to video if recording
            if video_recording:
                video_writer.write(frame)

            # Add status text and IP info to the frame
            status_text = "Ready"
            if receiving_mode:
                status_text = "Receiving mode active"
            elif video_recording:
                status_text = "Recording video..."
            
            cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display connection info
            ip_text = f"Your IP: {get_ip_address()}"
            partner_text = f"Partner: {partner_ip if partner_ip else 'Not set'}"
            cv2.putText(frame, ip_text, (10, frame.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, partner_text, (10, frame.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("AirShare - Gesture Recognition", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('p'):
                partner_ip = configure_partner_ip()

    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        print("\nCleaning up...")
        cap.release()
        if video_writer:
            video_writer.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_gestures()