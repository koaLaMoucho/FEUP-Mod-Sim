# server.py
from random import random
from mesa.visualization.modules import CanvasGrid, ChartModule
from mesa.visualization.ModularVisualization import ModularServer
from model import ParkingLotModel, ParkingSpace, Driver, Gate


def agent_portrayal(agent):
    if isinstance(agent, Gate):
        color = "black" if agent.kind == "IN" else "gray"
        return {
            "Shape": "rect",
            "w": 0.9,
            "h": 0.9,
            "Filled": "true",
            "Color": color,
            "Layer": 2,
        }

    if isinstance(agent, ParkingSpace):
        # color by space type (EV/PMR/GENERAL), then override if occupied
        if agent.space_type == "EV":
            color = "#88ccff"  # light blue for EV
        elif agent.space_type == "PMR":
            color = "#ffcc88"  # light orange for PMR
        else:
            color = "#cccccc"  # light gray for GENERAL

        if agent.occupied:
            color = "#ff4444"  # red if occupied (overrides type color)

        return {
            "Shape": "rect",
            "w": 0.9,
            "h": 0.9,
            "Filled": "true",
            "Color": color,
            "Layer": 0,
        }

    if isinstance(agent, Driver):
        # same colour for whole life, defined only in Driver.__init__
        color = agent.color

        if agent.state == "EXITING":
            # smaller square so it doesn’t paint the whole cell
            return {
                "Shape": "rect",
                "w": 0.4,
                "h": 0.4,
                "Filled": "true",
                "Color": color,
                "Layer": 3,
            }
        else:
            # normal circle
            return {
                "Shape": "circle",
                "r": 0.8,
                "Filled": "true",
                "Color": color,
                "Layer": 3,
            }




def make_server(port=8521):
    width, height = 35, 12

    grid = CanvasGrid(agent_portrayal, width, height, 500, 250)

    chart = ChartModule(
        [
            {"Label": "OccupiedSpaces", "Color": "#444444"},
            {"Label": "FreeSpaces", "Color": "#888888"},
            {"Label": "NumDrivers", "Color": "#0066cc"},
            {"Label": "CarsInside", "Color": "#00aa00"},
            {"Label": "CarsWaitingAtGate", "Color": "#aa0000"},
        ],
        data_collector_name="datacollector",
    )

    server = ModularServer(
        ParkingLotModel,
        [grid, chart],
        "Minimal Private Parking Lot",
        {
            "width": width,
            "height": height,
            "n_spaces": 14,
            "arrival_prob": 0.4,
            "n_ev": 4,
            "n_pmr": 2,
        },
    )
    server.port = port
    return server
