#!/usr/bin/env python
# coding: utf-8

# In[1]:


import cv2
import numpy as np
import pandas as pd
import time
import os
import torch
import math
import shapely.geometry
import matplotlib.pyplot as plt
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort


# In[2]:


device = "cuda" if torch.cuda.is_available() else "CPU"
print("Using device:", device)


# In[14]:


#directories
base_dir = os.getcwd()
video_path = os.path.join(base_dir, "construction15.mp4")
save_dir = os.path.join(base_dir, 'saved files')
intrusion_log_file =  os.path.join(save_dir, 'intrusion_log.txt')
violation_log_file =  os.path.join(save_dir, 'violation_log.txt')
print(base_dir)
print(save_dir)


# In[15]:


model_path = "training_result/safety_model6/weights/best.pt"
model = YOLO(model_path) #loading custm trained model
class_names = model.names #class label


# In[16]:


cap = cv2.VideoCapture(video_path)   #cv2.VideoCapture(0) for webcam
if not cap.isOpened():
    print("Error opening video")
    exit()

ret, firstframe = cap.read()
if not ret:
    print("Error reading first frame")
    cap.release()
    exit()


# In[17]:


frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))
print(f"Video Resolution: {frame_width} x {frame_height} \nFPS: {fps}")


# In[18]:


#restricted zone function
drawing = False
roi = ()
rx1 = ry1 = -1
temp = firstframe.copy()
def rect(event, rx2, ry2, flags, param):
    global drawing, roi, rx1, ry1, temp
    
    if event == cv2.EVENT_LBUTTONDOWN: #start drawing
        drawing = True
        rx1, ry1 = rx2, ry2
    
    elif event == cv2.EVENT_MOUSEMOVE and drawing: #updating while moving mouse for rectangle
        temp = firstframe.copy()
        cv2.rectangle(temp, (rx1, ry1), (rx2, ry2), (0, 255, 0), 2)
        cv2.imshow('Define Restricted Zone', temp)
    
    elif event == cv2.EVENT_LBUTTONUP: #final roi
        drawing = False
        
        rx_min = min(rx1, rx2)
        ry_min = min(ry1, ry2)
        rx_max = max(rx1, rx2)
        ry_max = max(ry1, ry2)
        
        roi = (rx_min, ry_min, rx_max, ry_max)
        temp = firstframe.copy()
        cv2.rectangle(temp, (rx_min, ry_min), (rx_max, ry_max), (0,255,0), 2)
        cv2.imshow('Define Restricted Zone', temp)


# In[30]:


#user input roi
cv2.imshow('Define Restricted Zone', firstframe)
cv2.setMouseCallback('Define Restricted Zone', rect)

new_roi = ()
while True:
    key = cv2.waitKey(0) & 0xff
    
    if key == ord('s') and roi:  #save roi
        rx1, ry1, rx2, ry2 = roi
        rx1, rx2 = sorted([int(rx1), int(rx2)])
        ry1, ry2 = sorted([int(ry1), int(ry2)])
        new_roi = (rx1, ry1, rx2, ry2)
        print("Saved ROI:", new_roi)
        break
    
    elif key == ord('r'):  #reset roi
        roi = ()
        temp = firstframe.copy()
        cv2.imshow('Define Restricted Zone', temp)
        
    elif key == ord('q'):
        cv2.destroyAllWindows()
        exit()

cv2.destroyAllWindows()


# In[31]:


#fps and status display
def fps_counts(frame, persons, ppe_results, prev_time):
    new_time = time.time()
    if prev_time:
        fps = 1 / (new_time - prev_time)
    else:
        fps = 0
    prev_time = new_time
    
    total_persons = len(persons)
    total_violations = 0
    for result in ppe_results:
        person_box = result[0]
        status = result[1]
        color = result[2]
        missing_items = result[3]
        
        if status != "SAFE":
            total_violations += 1

    cv2.putText(frame, f"FPS:{fps:.1f}" , (10, frame_height-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 100, 150), 2)
    cv2.putText(frame, f"Persons:{total_persons}", (10, frame_height-30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 100, 150), 2)
    cv2.putText(frame, f"PPE Violations:{total_violations}", (10,frame_height-50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 100, 150), 2)
    return frame, prev_time


# In[32]:


#intersection over union between two rectangles
def iou(boxA, boxB):
    ax1, ay1, ax2, ay2 = boxA 
    bx1, by1, bx2, by2 = boxB 

    xi1 = max(ax1, bx1)
    yi1 = max(ay1, by1)
    xi2 = min(ax2, bx2)
    yi2 = min(ay2, by2)

    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)

    boxA_area = (ax2 - ax1) * (ay2 - ay1)
    boxB_area = (bx2 - bx1) * (by2 - by1)

    union_area = boxA_area + boxB_area - inter_area

    if union_area == 0:
        return 0

    return inter_area / union_area


# In[33]:


def is_inside(person_box, object_box):
    px1, py1, px2, py2 = person_box
    ox1, oy1, ox2, oy2 = object_box

    ix1 = max(px1, ox1)
    iy1 = max(py1, oy1)
    ix2 = max(px2, ox2)
    iy2 = min(py2, oy2)

    return ix1 < ix2 and iy1 < iy2


# In[34]:


#detection of any intrusion in restricted area
def intrusion(cframe, rframe, roi, thresh, motion_pixel_count):
    global motion_pixels
    x1, y1, x2, y2 = roi
    gray_cf = cframe
    gray_rf = rframe
    
    diff = cv2.absdiff(gray_cf, gray_rf)
    roi_diff = diff[y1:y2, x1:x2]

    _, motion_mask = cv2.threshold(roi_diff, thresh, 255, cv2.THRESH_BINARY)
    motion_pixels = cv2.countNonZero(motion_mask)
    
    return motion_pixels > motion_pixel_count


# In[36]:


cap =  cv2.VideoCapture(video_path)
tracker = DeepSort(max_age=70, n_init=1)
grayframe1 = cv2.cvtColor(firstframe, cv2.COLOR_BGR2GRAY)
last_save_time = 0
intrusion_cooldown_seconds = 5
intrusion_detected = False
violation_cooldown = {}
violation_gap = 5
violation_logged = {}
prev_time = None

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        print("End of video")
        break
    raw_frame = frame.copy()
    results = model(frame, stream = True)
    grayframe2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    #intrusion detection
    if new_roi:
        if intrusion(grayframe2, grayframe1, new_roi, thresh=130, motion_pixel_count=100):
            color = (0,0,255)
            status = 'Intrusion Detected'
        else:
            color = (0,255,0)
            status = 'Clear'
        
        #draw roi and add status
        cv2.rectangle(frame, (new_roi[0], new_roi[1]), (new_roi[2], new_roi[3]), color, 2)
        cv2.putText(frame, status, (new_roi[0], new_roi[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        gray_visual = cv2.cvtColor(grayframe2, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(gray_visual, (new_roi[0], new_roi[1]), (new_roi[2], new_roi[3]), color, 2)
    else:
        gray_visual = cv2.cvtColor(grayframe2, cv2.COLOR_GRAY2BGR)
    
    #saving intrusion images if threshold exceedd
    if motion_pixels > 100:
        current_time = time.time()
        if current_time - last_save_time > intrusion_cooldown_seconds:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            image_path = os.path.join(save_dir, f"intrusion_{timestamp}.jpg")
            cv2.imwrite(image_path, frame)
            
            with open(intrusion_log_file, 'a') as log:
                log.write(f'Intrusion detected at {time.ctime()}\n')
            
            print(f"Intrusion detected and save at {timestamp}")
            intrusion_detected = True
            last_save_time = current_time

    #ppe detection
    persons = []
    helmets = []
    vests = []
    gloves = []
    detections = []
    
    for r in results:
        boxes = r.boxes
        
        if boxes is None:
            continue
            
        coords = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy()
        
        for i in range(len(coords)):
            x1, y1, x2, y2 = coords[i]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            conf_val = float(conf[i])
            if conf_val < 0.4:
                continue
            conf_dis = math.ceil((conf_val * 100)) /100
            cls = int(classes[i])
            label = class_names[cls]
            
            w, h = x2 - x1, y2 - y1
            
            if label == 'person': #person detection
                detections.append(([x1, y1, w, h], conf_val, cls))
                persons.append([x1, y1, x2, y2])
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 5, (255,0,255), -1)
                cv2.putText(frame, f"{label}:{conf_dis}", (cx, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,255), 2)
            
            if label == 'helmet':  #ppe detection
                helmets.append([x1, y1, x2, y2])
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 5, (255,0,255), -1)
                cv2.putText(frame, f"{label}:{conf_dis}", (cx, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,255), 2)
            if label == 'vest': 
                vests.append([x1, y1, x2, y2])
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 5, (255,0,255), -1)
                cv2.putText(frame, f"{label}:{conf_dis}", (cx, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,255), 2)
            if label == 'gloves': 
                gloves.append([x1, y1, x2, y2])
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 5, (255,0,255), -1)
                cv2.putText(frame, f"{label}:{conf_dis}", (cx, cy-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,255), 2)
        
        
        #ppe status for each person
        ppe_results = []
        missing_items = []

        for person in persons:
            helmet_found = False
            vest_found = False
            glove_found = False
            
            for helmet in helmets:
                if is_inside(person, helmet):
                    helmet_found = True
            
            for vest in vests:
                if is_inside(person, vest):
                    vest_found = True
                
            for glove in gloves:
                if is_inside(person, glove):
                    glove_found = True
            
            if helmet_found and vest_found and glove_found:
                status = 'SAFE'
                color = (0, 255, 0)

            elif helmet_found or vest_found or glove_found:
                status = 'PARTIAL PPE'
                color = (0, 255, 255)
            else:
                status = 'UNSAFE'
                color = (0, 0, 255)
            
            missing_items = []

            if not helmet_found:
                missing_items.append("No Helmet")
            if not vest_found:
                missing_items.append("No Vest")
            if not glove_found:
                missing_items.append("No Gloves")

            ppe_results.append((person, status, color, missing_items))
    
    #deepsort tracking
    tracks = tracker.update_tracks(detections, frame=frame)
    
    for track in tracks:
        if not track.is_confirmed():
            continue
            
        track_id = track.track_id
        track_class = track.det_class
        label = class_names[int(track_class)] if track_class is not None else "unknown"
        tx1, ty1, tx2, ty2 = track.to_ltrb() #left,top,right,bottom
        tx1, ty1, tx2, ty2 = int(tx1), int(ty1), int(tx2), int(ty2)
        
        if label == 'person':
            track_box = [tx1, ty1, tx2, ty2]
            best_iou = 0
            best_match = None

            for (pbox, status, color, missing_items) in ppe_results:
                iou_val = iou(pbox, track_box)

                if iou_val > best_iou:
                    best_iou = iou_val
                    best_match = (status, color, missing_items)

            if best_iou > 0.3:
                status, color, missing_items = best_match
                current_time = time.time()
                
                #log voilations
                if status != "SAFE" and missing_items:
                    if track_id not in violation_cooldown:
                        timestamp = time.strftime('%H:%M:%S')
                        violation_text = ", ".join(missing_items)
                        
                        ppe_image_path = os.path.join(save_dir, f'PPE_{track_id}_{timestamp}.jpg')
                        cv2.imwrite(ppe_image_path, frame)
                        print(f"PPE violation detectected and saved for ID {track_id} at {timestamp}")
                        log_text = f"ID: {track_id}: {violation_text} at {timestamp}\n"

                        with open(violation_log_file, 'a') as log:
                            log.write(log_text)

                        print("Logged:", log_text.strip())

                        violation_cooldown[track_id] = current_time

                cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), color, 2)
                cv2.putText(frame, f"ID:{track_id} {status}",(tx1, ty1-10),cv2.FONT_HERSHEY_SIMPLEX,0.6, color, 2)
    
    #cleaning so no repition again and again
    current_track_ids = [track.track_id for track in tracks if track.is_confirmed()]
    violation_logged = {tid: True for tid in violation_logged if tid in current_track_ids}
    
    #displaying fps and status
    frame, prev_time = fps_counts(frame, persons, ppe_results, prev_time)
    
    scale = 0.8 
    new_width = int(frame_width * scale)
    new_height = int(frame_height * scale)
    bgr_resized = cv2.resize(frame, (new_width, new_height))
    gray_resized = cv2.resize(gray_visual, (new_width, new_height))

    stacked = np.hstack((bgr_resized, gray_resized))  
    cv2.imshow("BGR and GRAYSCALE", stacked)
    if cv2.waitKey(1) & 0xFF == 27:
        break
        
cap.release()
cv2.destroyAllWindows()


# In[ ]:





# In[ ]:




