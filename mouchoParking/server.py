# server.py
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
        color = "#cccccc"
        if agent.occupied:
            color = "#ff5555"
        return {
            "Shape": "rect",
            "w": 0.9,
            "h": 0.9,
            "Filled": "true",
            "Color": color,
            "Layer": 0,
        }

    if isinstance(agent, Driver):
        return {
            "Shape": "circle",
            "r": 0.5,
            "Filled": "true",
            "Color": "#0066cc",
            "Layer": 3,
        }

    return {}


def make_server(port=8521):
    width, height = 10, 5

    grid = CanvasGrid(agent_portrayal, width, height, 500, 250)

    chart = ChartModule(
        [
            {"Label": "OccupiedSpaces", "Color": "#444444"},
            {"Label": "FreeSpaces", "Color": "#888888"},
            {"Label": "NumDrivers", "Color": "#0066cc"},
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
            "n_spaces": 4,
            "arrival_prob": 0.05,  # very few arrivals
            "max_cars": 3,
        },
    )
    server.port = port
    return server
