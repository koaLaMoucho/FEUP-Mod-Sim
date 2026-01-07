# server.py
from random import random
from mesa.visualization.modules import CanvasGrid, ChartModule, TextElement
from mesa.visualization.ModularVisualization import ModularServer
from model import ParkingLotModel, ParkingSpace, Driver, Gate , VIPParkingSpace

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
    
    if isinstance(agent, VIPParkingSpace):
        # safe checks for reservation attributes
        color = "#00bfff"
        if False : #agent.occupied:
            color = "#ff5555"  # occupied
        elif agent.is_reserved:
            color = "#ffccaa"  # reserved free spot (different color for VIP)
        return {
            "Shape": "rect",
            "w": 0.9,
            "h": 0.9,
            "Filled": "true",
            "Color": color,
            "Layer": 0,
        }
    elif isinstance(agent, ParkingSpace):
        # safe checks for reservation attributes
        color = "#cccccc"
        if agent.occupied:
            color = "#ff5555"  # occupied
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
    def render(self, model):
        arrivals = model.total_arrivals

        didnt_enter = model.total_not_entered_long_queue + model.total_price_turnaways

        avg_queue_time = (
            model.total_queue_time / model.total_queued_drivers
            if model.total_queued_drivers > 0
            else 0.0
        )

        total_res = getattr(model, "total_reservations", 0)
        res_fulfilled = getattr(model, "total_reservations_fulfilled", 0)

        reserved_idle = sum(
            1
            for s in getattr(model, "parking_spaces", [])
            if getattr(s, "is_reserved", False)
            and not s.occupied
        )

        # --- CSS STYLING APPLIED HERE ---
        # position: fixed -> Keeps it on the screen even if you scroll
        # left: 20px -> Anchors it to the empty left space
        # top: 100px -> Pushes it down below the Mesa header/navbar
        return f"""
        <div style="
            position: fixed; 
            top: 100px; 
            left: 20px; 
            width: 280px; 
            background-color: white; 
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
            font-family: monospace; 
            font-size: 13px; 
            padding: 15px;
            z-index: 1000;
        ">
            <h3 style="margin-top:0; border-bottom: 2px solid #333; padding-bottom:5px;">📊 Simulation KPIs</h3>

            <b>Step:</b> {model.current_step}<br><br>

            <h4 style="margin-bottom:5px; color: #444;">🚗 Traffic</h4>
            <table style="width:100%">
                <tr><td>Total Arrivals</td><td style="text-align:right">{arrivals}</td></tr>
                <tr><td>Did Not Enter</td><td style="text-align:right">{didnt_enter}</td></tr>
            </table>

            <h4 style="margin-bottom:5px; color: #444;">⏱ Queue</h4>
            <table style="width:100%">
                <tr><td>Total Queue Time</td><td style="text-align:right">{model.total_queue_time}</td></tr>
                <tr><td>Queued Drivers</td><td style="text-align:right">{model.total_queued_drivers}</td></tr>
                <tr><td>Avg Queue Time</td><td style="text-align:right">{avg_queue_time:.2f}</td></tr>
            </table>

            <h4 style="margin-bottom:5px; color: #444;">🅿️ Reservations</h4>
            <table style="width:100%">
                <tr><td>Mode</td><td style="text-align:right">{getattr(model, 'reservation_mode', 'none')}</td></tr>
                <tr><td>Scheduled</td><td style="text-align:right">{total_res}</td></tr>
                <tr><td>Fulfilled</td><td style="text-align:right">{res_fulfilled}</td></tr>
                <tr><td>Idle Reserved</td><td style="text-align:right">{reserved_idle}</td></tr>
            </table>

            <h4 style="margin-bottom:5px; color: #444;">💰 Financials</h4>
            <table style="width:100%">
                <tr><td>Strategy</td><td style="text-align:right">{model.parking_strategy}</td></tr>
                <tr><td>Rate (€/min)</td><td style="text-align:right">€{getattr(model, 'current_per_minute_rate', model.base_per_minute):.3f}</td></tr>
                <tr><td>Total Revenue</td><td style="text-align:right">€{getattr(model, 'total_revenue', 0.0):.2f}</td></tr>
                <tr><td>Lost (Price)</td><td style="text-align:right">{getattr(model, 'total_price_turnaways', 0)}</td></tr>
            </table>
        </div>
        """

def make_server(port=8521):
    width, height = 50, 20

    grid = CanvasGrid(agent_portrayal, width, height, 500, 360)

    # Note: canvas_width reduced slightly to 800 to accommodate sidebar
    # Main chart: occupancy and cars inside
    main_chart = ChartModule(
        [
            {"Label": "OccupiedSpaces", "Color": "#444444"},
            {"Label": "FreeSpaces", "Color": "#888888"},
            {"Label": "CarsInside", "Color": "#00aa00"},
        ],
        data_collector_name="datacollector",
        canvas_width=800, 
        canvas_height=250,
    )

    # Queue / congestion chart
    queue_chart = ChartModule(
        [
            {"Label": "CarsWaitingAtGate", "Color": "#aa0000"},
            {"Label": "NumDrivers", "Color": "#0066cc"},
        ],
        data_collector_name="datacollector",
        canvas_width=800,
        canvas_height=250,
    )

    # Reservation chart
    reservation_chart = ChartModule(
        [
            {"Label": "ReservationsFulfilled", "Color": "#00cc00"},
            {"Label": "ReservationsReleased", "Color": "#cc6600"},
            {"Label": "ReservedIdleSpaces", "Color": "#0066cc"},
        ],
        data_collector_name="datacollector",
        canvas_width=800,
        canvas_height=250,
    )

    kpi_panel = KPIPanel()

    server = ModularServer(
        ParkingLotModel,
        [grid, main_chart, queue_chart, reservation_chart, kpi_panel],
        "Minimal Private Parking Lot",
        {
            "width": width,
            "height": height,
            "n_spaces": 10,
            "parking_strategy": "Dynamic Pricing", 
            "reservation_percent": 0.20,             
            "reservation_hold_time": 30,              
            "day_length_steps": 1000,
            "arrival_prob": 0.7,        
        },
    )
    server.max_steps = 1000
    server.port = port
    return server