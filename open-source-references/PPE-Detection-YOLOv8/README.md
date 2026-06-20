# AI Based Safety Monitoring and Violation Management System Using YOLOv8 and DeepSORT



## Introduction

This project is designed to monitor safety compliance in construction environments . It detects Personal Protective Equuipment (PPE) usage and identifies intrusions in restricted areas. It combines **YOLOv8 object detection** and **DeepSort tracking** to detect:

* PPE (Personal Protective Equipment) compliance:

    - Helmets
    - Vests
    - Gloves

* Intrusions into restricted zones.

It also logs **violations** and **intrusion events** with timestamps and saves snapshots for further analysis.



## Features

1. **Person Detection** – Detects workers on site.
2. **PPE Detection** – Identifies missing safety equipment.
3. **ROI (Restricted Area)** - Lets user select desired ROI via mouse
4. **Restricted Zone Monitoring** – Detects intrusion events using motion analysis in user defined areas.
5. **DeepSort Tracking** – Multi-object tracking that maintains consistent IDs for workers.
6. **Automatic Logging** – Stores PPE violations and intrusion events with timestamps.
7. **Automatic image capture** - Saves image at time of violations
8. **Visualization** – Displays both colored video and grayscale motion-detection view side by side.
8. **Lightweight & Flexible** – Can run on different video resolutions and supports GPU acceleration if available.



## Project Structure
```
├── saved files/           # Intrusion and PPE violationsnapshots, logs
├── training_result/       
│   └── safety_model6/     
│       └── weights/       
│           └── best.pt    # Custom YOLOv8 trained weights
├── data.yaml              # Dataset configuration for training
├── train_model.ipynb      # Jupyter Notebook used for training
├── yolov8n.pt             # YOLOv8 pretrained weights
├── construction15.mp4     # Sample video 
├── requirements.txt       # Python dependencies 
└── README.md              # Project description
```


## System Workflow \& How-to Guide

1. Your input video should be in project folder
2. Run the main script main.py
3. Define a Restricted Zone by drawing a rectangle with the mouse:

    - Press s to save the ROI.

    - Press r to reset.

    - Press q to quit.

4. Detect persons using YOLOv8
5. Detect PPE items (helmet, vest, gloves)
6. Match PPE with each person
7. Classify safety status:

    - SAFE

    - PARTIAL PPE

    - UNSAFE

8. Track individuals using DeepSORT
9. Detect intrusion in restricted zones
10. Log violations and save files/intrusion_log.txt and saved files/violation_log.txt.
11. Save snapshots of detected violations in saved files.
12. Real-time annotated video display



## Output

![alt test](https://github.com/Aroomaa/PPE-Compliance-and-Detection-using-YOLOv8-DeepSORT/blob/be2cebcf84d3f8b9bb7ff1f696b4b68b4458a69b/output/sample\_output1.png)


> ## Notes

> * Thresholds and parameters (like threshold, motion pixel count, confidence, and FPS scaling) can be modified in the script for different site environments.
> * The system supports variable video resolutions and adapts to the original input size.
> * The model was trained on custom datasets for detecting construction safety equipment.

