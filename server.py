# server.py
from random import random
from mesa.visualization.modules import CanvasGrid, ChartModule, TextElement
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


class KPIPanel(TextElement):
    """
    Text panel to display cumulative KPIs during the run.
    """

    def render(self, model):
        if model.total_arrivals > 0:
            turn_away_rate = model.total_turned_away / model.total_arrivals
        else:
            turn_away_rate = 0.0
        
        if model.total_balked > 0:
            balk_rate = model.total_balked / model.total_arrivals
        else:
            balk_rate = 0.0

        if model.total_queued_drivers > 0:
            avg_queue_time = model.total_queue_time / model.total_queued_drivers
        else:
            avg_queue_time = 0.0

        lines = [
            f"Step: {model.current_step}",
            "",
            f"Total Arrivals: {model.total_arrivals}",
            f"Turned Away (total): {model.total_turned_away}",
            f"  - Not entered (long queue): {model.total_not_entered_long_queue}",
            f"  - Balked (left queue): {model.total_balked}",
            f"Turn-Away Rate: {turn_away_rate:.3f}",
            f"Balk Rate: {balk_rate:.3f}",
            "",
            f"Total Queue Time: {model.total_queue_time}",
            f"Queued Drivers (that entered): {model.total_queued_drivers}",
            f"Avg Queue Time: {avg_queue_time:.3f}",
            "",
            f"Max Queue Length (param): {model.max_queue_length}",
            f"Max Wait Time (param): {model.max_wait_time}",
            "",
            f"Total Revenue: {getattr(model, 'total_revenue', 0.0):.2f}",
            #arrival prob
            f"Arrival Probability (param): {model.arrival_prob * model.arrival_prob_at_step(model.current_step):.3f}"
        ]
        return "\n".join(lines)




def make_server(port=8521):
    width, height = 50, 20

    grid = CanvasGrid(agent_portrayal, width, height, 500, 250)

    # Main chart: occupancy and cars inside
    main_chart = ChartModule(
        [
            {"Label": "OccupiedSpaces", "Color": "#444444"},
            {"Label": "FreeSpaces", "Color": "#888888"},
            {"Label": "CarsInside", "Color": "#00aa00"},
        ],
        data_collector_name="datacollector",
    )

    # Queue / congestion chart
    queue_chart = ChartModule(
        [
            {"Label": "CarsWaitingAtGate", "Color": "#aa0000"},
            {"Label": "NumDrivers", "Color": "#0066cc"},
        ],
        data_collector_name="datacollector",
    )

    kpi_panel = KPIPanel()

    server = ModularServer(
        ParkingLotModel,
        [grid, main_chart, queue_chart, kpi_panel],
        "Minimal Private Parking Lot",
        {
            "width": width,
            "height": height,
            "n_spaces": 16
        },
    )
    server.port = port
    return server
