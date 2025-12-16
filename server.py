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
        # safe checks for reservation attributes
        is_reserved = getattr(agent, "is_reserved", False)
        held = getattr(agent, "held", False)
        color = "#cccccc"
        if agent.occupied:
            color = "#ff5555"  # occupied
        elif held:
            color = "#ffcc66"  # reserved but held (no-show hold)
        elif is_reserved:
            color = "#cceeff"  # reserved free spot
        return {
            "Shape": "rect",
            "w": 0.9,
            "h": 0.9,
            "Filled": "true",
            "Color": color,
            "Layer": 0,
        }

    if isinstance(agent, Driver):
        # 1. Get the base color
        color = agent.color
        
        # 2. Define the base portrayal dictionary
        portrayal = {
            "Filled": "true",
            "Color": color,
            "Layer": 3,
        }

        # 3. If VIP, add the "V"
        if getattr(agent, "reserved_customer", False):
            portrayal["text"] = "V"
            portrayal["text_color"] = "white" # White text stands out on dark colors

        # 4. Handle Shape based on state (Exiting vs Normal)
        if agent.state == "EXITING":
            portrayal["Shape"] = "rect"
            portrayal["w"] = 0.4
            portrayal["h"] = 0.4
        else:
            portrayal["Shape"] = "circle"
            portrayal["r"] = 0.8
            
        return portrayal


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

        # reservation KPIs (use getattr for backward compatibility)
        total_res = getattr(model, "total_reservations", 0)
        res_fulfilled = getattr(model, "total_reservations_fulfilled", 0)
        res_released = getattr(model, "total_reservations_released", 0)
        reserved_idle = sum(
            1 for s in getattr(model, "parking_spaces", []) if getattr(s, "is_reserved", False) and not s.occupied and not getattr(s, "held", False)
        )


        current_price_display = f"€{model.base_price:.2f}"
        
        if model.parking_strategy == "Dynamic Pricing":
            current_price_display = f"€{getattr(model, 'current_price', 0):.2f} (Dynamic)"
        elif model.parking_strategy == "Reservations":
             current_price_display = f"€{model.base_price:.2f} (Standard) / €15.00 (VIP)"
        
        revenue = getattr(model, "total_revenue", 0.0)

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
            f"Arrival Probability (param): {model.arrival_prob * model.arrival_prob_at_step(model.current_step):.3f}",
            f"Reservation mode: {getattr(model, 'reservation_mode', 'none')}",
            f"Total Reservations (scheduled): {total_res}",
            f"Reservations Fulfilled: {res_fulfilled}",
            f"Reservations Released (no-show released): {res_released}",
            f"Reserved idle spaces: {reserved_idle}",
            "--- FINANCIALS ---",
            f"Dynamic Pricing: {'ON' if model.parking_strategy == 'Dynamic Pricing' else 'OFF'}",
            f"Current Price: ${getattr(model, 'current_price', 0):.2f}",
            f"Total Revenue: ${getattr(model, 'total_revenue', 0.0):.2f}",
            f"Lost Customers (Price): {getattr(model, 'total_price_turnaways', 0)}",
            

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

    # Reservation chart
    reservation_chart = ChartModule(
        [
            {"Label": "ReservationsFulfilled", "Color": "#00cc00"},
            {"Label": "ReservationsReleased", "Color": "#cc6600"},
            {"Label": "ReservedIdleSpaces", "Color": "#0066cc"},
        ],
        data_collector_name="datacollector",
    )

    kpi_panel = KPIPanel()

    server = ModularServer(
        ParkingLotModel,
        [grid, main_chart, queue_chart, reservation_chart, kpi_panel],
        "Minimal Private Parking Lot",
        {
            "width": width,
            "height": height,
            "n_spaces": 16,
            "parking_strategy": "Dynamic Pricing",  # "Standard", "Dynamic Pricing", "Reservations"
            "reservation_percent": 0.20,               # fraction of spots reserved (0..1)
            "reservation_hold_time": 50,               # steps to hold after no-show
            "reservation_no_show_prob": 0.1,           # probability a reserved driver no-shows
            
        },
    )
    server.port = port
    return server
