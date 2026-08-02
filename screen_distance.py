import cv2
import mediapipe as mp
import math

# --- 1. CONFIGURATION PARAMETERS ---
# Approximate focal length in pixels for a standard 60-degree horizontal FOV webcam at 640x480 resolution
# Formula: f_pixels = (width / 2) / tan(horizontal_FOV_rad / 2)
FOCAL_LENGTH_PIXELS = 554.0 

# Average real-world human IRIS diameter in centimeters (highly stable at ~11.7mm)
TRUE_IRIS_DIAMETER_CM = 1.17 

# Distance threshold: warning triggers if user is closer than this distance (in cm)
TOO_CLOSE_THRESHOLD_CM = 40.0 

# --- 2. INITIALIZE MEDIAPIPE FACE MESH ---
# refine_landmarks=True is REQUIRED to unlock the 473-landmark model containing precise iris boundaries
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True, 
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# Open webcam stream
cap = cv2.VideoCapture(0)

print("Starting Iris Distance Tracker... Press 'q' to quit.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # Mirror the frame horizontally for standard selfie view, convert from BGR to RGB
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_h, img_w, _ = frame.shape
    
    # Process face landmarks
    results = face_mesh.process(rgb_frame)
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            
            # MediaPipe Left Iris Landmarks:
            # 468: Center, 469: Right boundary, 470: Top, 471: Left boundary, 472: Bottom
            # We select landmark 469 (inner/right side) and 471 (outer/left side) to get horizontal diameter
            p_left_edge = face_landmarks.landmark[471]
            p_right_edge = face_landmarks.landmark[469]
            
            # Convert normalized coordinates (0.0 to 1.0) into pixel coordinates
            x1, y1 = int(p_left_edge.x * img_w), int(p_left_edge.y * img_h)
            x2, y2 = int(p_right_edge.x * img_w), int(p_right_edge.y * img_h)
            
            # Calculate the perceived iris width in pixels via Euclidean distance formula
            perceived_width_pixels = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            if perceived_width_pixels > 0:
                # --- 3. CALCULATE DISTANCE FROM WEBCAM ---
                # Distance (cm) = (Focal Length in pixels * True Physical Size in cm) / Perceived Pixel Size
                calculated_distance_cm = (FOCAL_LENGTH_PIXELS * TRUE_IRIS_DIAMETER_CM) / perceived_width_pixels
                
                # Draw bounding dots on the monitored iris edges
                cv2.circle(frame, (x1, y1), 3, (0, 255, 255), -1) # Yellow dots
                cv2.circle(frame, (x2, y2), 3, (0, 255, 255), -1)
                
                # --- 4. CLOSE DISTANCE EVALUATION ---
                if calculated_distance_cm < TOO_CLOSE_THRESHOLD_CM:
                    warning_text = "TOO CLOSE TO CAMERA!"
                    print(f"Warning: {warning_text} ({calculated_distance_cm:.1f} cm)")
                    # Visual red warning text
                    cv2.putText(frame, warning_text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                else:
                    status_text = f"Distance: {calculated_distance_cm:.1f} cm"
                    # Visual blue tracking text
                    cv2.putText(frame, status_text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 0), 2)

    # Display the visual feedback window
    cv2.imshow('Webcam Iris Distance Tracker', frame)
    
    # Break loop safely if 'q' key is pressed
    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
