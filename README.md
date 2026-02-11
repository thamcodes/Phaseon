<h1 align="center">Phaseon</h1>
<p align="center">
A real-time EEG-driven prosthetic arm control system
</p>

<p align="center">
  <img src="assets/readme-images/prosthetic-arm-complete.jpeg" alt="Phaseon Prosthetic Arm" width="260">
</p>

---

## 🧠 About Phaseon

> ⚠️ *Phaseon is currently under active development.  
The system architecture and results will evolve as each phase is completed.
>
> This project is being carried under ITIE Knowledge Solutions Pvt. Ltd.*

**Phaseon** is an ongoing research and engineering project that focuses on building a  
**real-time EEG-controlled 3D-printed prosthetic arm** for basic hand interaction.

The system is designed to acquire brain signals, process them in real time, and translate
the extracted patterns into **grip and release commands** for a prosthetic hand.

This project primarily aims to explore:

- Real-time EEG signal acquisition,
- Signal preprocessing and feature extraction,
- Machine-learning-based intent classification,
- Low-latency hardware actuation for assistive robotics.

---

## 🤖 Hardware

The mechanical structure of the prosthetic hand is based on the  
**InMoov Right Hand open-source design**.

- Total printed parts: **67**
- Printing material: **PLA filament**
- Assembly: Fully articulated fingers and thumb suitable for tendon-based actuation

---

## ⚡ Electronics & Circuit

The prosthetic arm is driven using the following main components:

- **MG996R servo motors**
- **PCA9685 16-channel servo driver**
- **LiFePO battery pack**
- **Arduino Uno**

The PCA9685 driver is used to enable stable multi-servo control while keeping the
microcontroller load minimal.

---

## 🧩 System Overview

The Phaseon system follows a closed-loop real-time control pipeline:

1. EEG signal acquisition
2. Signal preprocessing and noise removal
3. Feature extraction
4. Classification of motor intent
5. Command generation
6. Servo-level actuation of the prosthetic hand

---

## ⏳ Project Phases

The project is developed in structured phases.

### Phase 1 – Real-time EEG Interface & Processing (Ongoing)

A real-time **Graphical User Interface (GUI)** is being developed to:

- Establish communication with the EEG acquisition device,
- Stream EEG data live,
- Perform preprocessing and visualization,
- Provide a foundation for downstream machine learning models.

This phase focuses on building a reliable software pipeline before full hardware-in-the-loop control.

Future phases will integrate classification and closed-loop prosthetic control.

---

## 🔭 Planned Phases

- Real-time EEG feature extraction and dataset creation
- Machine learning model for grip / release intent detection
- Real-time command mapping to servo motion
- Closed-loop validation with the prosthetic arm

---

## 🛠️ Tech Stack

- Python (signal processing, visualization, GUI, ML)
- PyQt / PyQtGraph (real-time interface and plots)
- Arduino (low-level motor control)
- I²C communication with PCA9685

---

## 📌 Project Status

🚧 Actively under development  
This repository currently contains the software and hardware foundations for the Phase 1 pipeline.

---

## 👥 Authors
1. Thammanna Sampras
2. Vishal KL
3. Prerna Balaji
4. Sai Niharika A

   
<p align = center>💫Thanks for stopping by!</p>
