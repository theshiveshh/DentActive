import argparse
import io
from PIL import Image
import datetime
from damage_detector import DamageDetector

import torch
import cv2
import numpy as np
import tensorflow as tf
from re import DEBUG, sub
from flask import Flask, render_template, request, redirect, send_file, url_for, Response
from werkzeug.utils import secure_filename, send_from_directory
import os
import subprocess
from subprocess import Popen
import re
import requests
import shutil
import time
import glob
from ultralytics import YOLO

app = Flask(__name__)


@app.route("/")
def hello_world():
    return render_template('index.html')


@app.route("/", methods=["GET", "POST"])
def predict_img():
    if request.method == "POST":
        if 'file' in request.files:
            f = request.files['file']
            basepath = os.path.dirname(__file__)
            filepath = os.path.join(basepath, 'uploads', f.filename)
            print("upload folder is ", filepath)
            f.save(filepath)
            global imgpath
            predict_img.imgpath = f.filename
            print("printing predict_img :::::: ", predict_img)

            file_extension = f.filename.rsplit('.', 1)[1].lower()
            if file_extension == 'jpg':

                img = cv2.imread(filepath)
                frame = cv2.imencode('.jpg', cv2.UMat(img))[1].tobytes()
                image = Image.open(io.BytesIO(frame))
                yolo = YOLO('best.pt')
                results = yolo.predict(
                    image, hide_conf=True, retina_masks=True, save=True)

                # Create an instance of your DamageDetector class
                detector = DamageDetector()

                # Find the latest saved image
                folder_path = 'runs/segment'
                subfolders = [k for k in os.listdir(
                    folder_path) if os.path.isdir(os.path.join(folder_path, k))]
                latest_subfolder = max(subfolders, key=lambda x: os.path.getctime(
                    os.path.join(folder_path, x)))
                directory = folder_path+'/'+latest_subfolder
                files = os.listdir(directory)
                latest_file = files[0]
                filename = os.path.join(
                    folder_path, latest_subfolder, latest_file)

                # Read the saved image using OpenCV's imread function
                saved_image = cv2.imread(filename)

                # Loop through each detection
                for detection in results:
                    # Get the bounding box coordinates
                    # box with xyxy format, (N, 4)
                    boxes = detection.boxes.xyxy
                    for box in boxes:
                        x1, y1, x2, y2 = box.numpy()
                        # Crop the image to the bounding box
                        cropped_image = image.crop((x1, y1, x2, y2))
                        # Save the cropped image to a temporary file
                        cropped_image.save('temp.jpg')
                        # Use your library to predict the severity of the damage
                        severity = detector.predict_severity('temp.jpg')
                        # Draw the severity text on the saved image using OpenCV
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        text = f"Severity : {severity*10}%"
                        text_size = cv2.getTextSize(text, font, 1, 2)[0]
                        text_x = int(x2-150)
                        text_y = int(y1 - 10)
                        cv2.putText(saved_image, text, (text_x, text_y),
                                    font, 0.6, (0, 0, 0), thickness=4)

                        cv2.putText(saved_image, text, (text_x, text_y),
                                    font, 0.6, (255, 255, 255), thickness=1)

                        os.remove('temp.jpg')
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                font_color = (255, 255, 255) # white
                thickness = 2

                text1 = "Original"
                text_size1 = cv2.getTextSize(text1, font, font_scale, thickness)[0]
                text_x1 = (img.shape[1] - text_size1[0]) // 2
                text_y1 = text_size1[1] + 10
                line_y1=  text_y1-12
                cv2.line(img, (0, line_y1), (img.shape[1], line_y1), (0, 0, 0), 30)
                cv2.putText(img, text1, (text_x1, text_y1), font, font_scale, font_color, thickness)
                
                
                text2 = "Detected"
                text_size2 = cv2.getTextSize(text2, font, font_scale, thickness)[0]
                text_x2 = (saved_image.shape[1] - text_size2[0]) // 2
                text_y2 = text_size2[1] + 10
                line_y2=  text_y2-12
                cv2.line(saved_image, (0, line_y2), (saved_image.shape[1], line_y2), (0, 0, 0), 30)
                cv2.putText(saved_image, text2, (text_x2, text_y2), font, font_scale, font_color, thickness)

                # Save the resulting image with the severity text drawn on it in the same location as the original saved image
                gap_width = 50
                background_color = (0, 0, 0) # black
                gap_image = np.full((max(img.shape[0], saved_image.shape[0]), gap_width, 3), background_color, dtype=np.uint8)
                saved_image=cv2.hconcat([img,gap_image,saved_image])
                print("printing directory: ", filename)
                cv2.imwrite(filename, saved_image)
                return display(f.filename)
                # Do segmentation and damage detection


            elif file_extension == 'mp4':
                video_path = filepath  # replace with your video path
                cap = cv2.VideoCapture(video_path)
                # get video dimensions
                frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                # Define the codec and create VideoWriter object
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(
                    'output.mp4', fourcc, 30.0, (frame_width, frame_height))
                # initialize the YOLOv8 model here
                model = YOLO('best.pt')
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    # do YOLOv8 detection on the frame here
                    results = model(frame, save=True)  # working
                    print(results)
                    cv2.waitKey(1)
                    res_plotted = results[0].plot()
                    cv2.imshow("result", res_plotted)
                    # write the frame to the output video
                    out.write(res_plotted)
                    if cv2.waitKey(1) == ord('q'):
                        break
                    # for result in results:
                    # #class_id, confidence, bbox = result
                    # boxes = result.boxes # Boxes object for bbox outputs
                return video_feed()

    folder_path = 'runs/segment'
    subfolders = [f for f in os.listdir(
        folder_path) if os.path.isdir(os.path.join(folder_path, f))]
    latest_subfolder = max(subfolders, key=lambda x: os.path.getctime(
        os.path.join(folder_path, x)))
    image_path = folder_path+'/'+latest_subfolder+'/'+f.filename
    return render_template('index.html', image_path=image_path)


@app.route('/<path:filename>')
def display(filename):
    folder_path = 'runs/segment'
    subfolders = [f for f in os.listdir(
        folder_path) if os.path.isdir(os.path.join(folder_path, f))]
    latest_subfolder = max(subfolders, key=lambda x: os.path.getctime(
        os.path.join(folder_path, x)))
    directory = folder_path+'/'+latest_subfolder
    print("printing directory: ", directory)
    files = os.listdir(directory)
    latest_file = files[0]

    print(latest_file)

    filename = os.path.join(folder_path, latest_subfolder, latest_file)
    file_extension = filename.rsplit('.', 1)[1].lower()
    environ = request.environ
    if file_extension == 'jpg':
        return send_from_directory(directory, latest_file, environ)

    else:
        return "Invalid file format"


def get_frame():
    folder_path = os.getcwd()
    mp4_file='output.mp4'
    video = cv2.VideoCapture(mp4_file)
    while True:
        success, image = video.read()
        if not success:
            break
        ret, jpeg = cv2.imencode('.jpg',image)
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n'+jpeg.tobytes()+b'\r\n\r\n')
        time.sleep(0.1)

# function to display the detected objects video on html page
@app.route("/video_feed")
def video_feed():
    return Response(get_frame(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flask app exposing yolov5 models")
    parser.add_argument("--port", default=5000, type=int, help="port number")
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)