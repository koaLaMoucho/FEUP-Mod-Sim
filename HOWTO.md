# Mod & Sim: Parking Lot Simulation
## Delivery Organizations
Slide-deck presentations: docs folder
Report: PDF in docs folder and Overleaf shared link at the bottom of the page
Short Video: Link at the bottom of the page
Source code: Python files
HOWTO file is this one

## Overview
Parking management, especially in urban areas of high demand, poses a challenge for highly populated cities, such as Porto and Lisbon, which is caused by the scarcity of the resources and the stochastic nature of the driver’s behavior. This project aims to understand the parking allocation problem and solve it by modeling the interactions between drivers and the infrastructure to evaluate the different management strategies. 

It implements an Agent-Based Model (ABM) developed in Python language using the MESA framework. Drivers are deployed as autonomous agents with their own state machines, ranging from queuing to parking and exiting. The program evaluates multiple scenarios, including a standard First Come First Serve (FCFS), reservation based approach and dynamic pricing approach that adapts the charge rate based on factors such as the occupancy and driver willingness to pay. 

From each simulation, the model generates values for key performance indicators (KPI), such as occupancy rates, queue times, revenue and among others. The main findings of this project are only to provide information and to identify which policies were the most effective.

## Features
- **Agent-Based Modeling**: Drivers and parking spaces as agents with states and behaviors.
- **Parking Strategies**: Standard, dynamic pricing based on occupancy, and reservation-based systems.
- **Visualization**: Interactive grid view, charts for occupancy, queues, and reservations, plus a KPI dashboard.
- **KPIs**: Tracks arrivals, queue times, revenue, occupancy rates, and reservation metrics.
- **Configurable Parameter**: Strategy selection 

## Installation
1. Clone or download the project to your local machine.
2. Navigate to the project directory.
3. Install dependencies from `requirements.txt` by running:
   ```
   pip install -r requirements.txt
   ```
    This installs Mesa (version 2.3.2) and other required packages.

## Usage
### Running the Simulation
1. To start the web-based visualization server:

- Execute the following command in the terminal:
   ```
   python run.py
   ```
- Click "Start" to run the simulation and "Stop" to pause it. "Step" advances the simulation by one step.

2. The simulation runs for a set number of steps ( 1000, representing 16 hours in real life).
- Charts and KPI panel update in real-time to reflect the current state of the simulation.
3. To change the strategy, modify the `"parking_strategy": ..., ` parameter in `server.py` to one of the following options:
   - `"Standard"`: First Come First Serve (FCFS)
   - `"Dynamic Pricing"`: Dynamic pricing based on occupancy
   - `"Reservations"`: Reservation-based parking system

### Key Files
- `model.py`: Core simulation logic, agents, and model class.
- `server.py`: Visualization server setup with charts and UI.
- `run.py`: Entry point to start the simulation server.
- `requirements.txt`: Python dependencies.

## Requirements
- Python 3.10+
- Mesa 2.3.2 (installed via `requirements.txt`)


## Important Links

- [Project Report](https://www.overleaf.com/read/krmqwqbwgrjh#fad616)
