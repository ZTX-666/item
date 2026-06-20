#!/usr/bin/env python
# coding: utf-8

# In[11]:


from ultralytics import YOLO
import torch
import os

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

base_dir = os.getcwd()
print(base_dir)
data_yaml = os.path.join(base_dir, "dataset", "data.yaml")
print(data_yaml)
# data_yaml = "data.yaml"
model = YOLO("yolov8n.pt")  

model.train(
    data=data_yaml,   #YAML file
    epochs=60,           # reduce if needed
    imgsz=416,
    batch=8,             # reduce to 4 if memory issues
    device=device,
    workers=0,
    project="training_result",
    name="safety_model",
    pretrained=True
)

print("Training finished.")


# In[ ]:




