from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import math, random


def parking_duration_steps(rng=random):
    """
    Mixture model for parking durations (in steps).
    - short stays:  15% of drivers
    - normal stays: 60%
    - long stays:  25%
    1 step = 1 minute
    """
    u = rng.random()

    # Short stay (e.g., quick errand)
    if u < 0.15:
        return rng.randint(40, 140)

    # Normal stay
    if u < 0.65:
        return rng.randint(240, 300)

    # Long stay
    return rng.randint(300, 700)

class ParkingSpace(Agent):
    def __init__(self, unique_id, model, pos):
        super().__init__(unique_id, model)
        self.pos = pos
        self.occupied = False
        self.occupant_id = None
        self.is_reserved = False


    def step(self):
        pass


class Gate(Agent):
    def __init__(self, unique_id, model, pos, kind):
        super().__init__(unique_id, model)
        self.pos = pos
        self.kind = kind
    def step(self):
        pass


class Driver(Agent):
    def __init__(self, unique_id, model, parking_duration=None, reserved=False, reservation=None):
        super().__init__(unique_id, model)
        self.state = "ARRIVING"
        self.waiting_for_gate = False
        self.belt_lane_y = None
        self.color = "#%06x" % self.random.randrange(0, 0xFFFFFF)
        
        self.target_space_id = None
        self.current_space_id = None

        #Reservation info
        self.reserved_customer = reserved
        self.reservation = reservation 

        if self.reserved_customer and self.reservation is not None:
            self.target_space_id = reservation['space_id']
            # As soon as this agent is created, we check the spot and boot anyone there.
            if self.target_space_id is not None:
                self.force_eviction_of_occupant(self.target_space_id)

        self.parking_duration = parking_duration or parking_duration_steps(rng=self.random)
        self.remaining_time = self.parking_duration

        # --- timestamps para KPIs ---
        self.arrival_step = None
        self.queue_entry_step = None
        

    def step(self):

        # ---------------- ARRIVING ----------------
        if self.state == "ARRIVING":
            entry_pos = self.model.entry_gate.pos
            self.model.grid.place_agent(self, entry_pos)
            self.state = "APPROACHING_GATE"
            return

        # ---------------- APPROACHING_GATE ----------------
        if self.state == "APPROACHING_GATE":
            gx, gy = self.model.entry_gate_2.pos
            x, y = self.pos

            if (x, y) == (gx, gy):
                can_enter = False
                if self.reserved_customer:
                    # VIPs always try to enter. If spot is occupied, we will have booted the occupant.
                    # However, physically it might still be full. The VIP waits or enters.
                    # For simplicity, VIP enters if the reservation is valid.
                    can_enter = True 
                else:
                    if self.model.free_unreserved_capacity() > 0:
                        can_enter = True
                
                if can_enter:
                    # customer didnt have to wait queue was empty
                    self.model.total_queue_time += 0 
                    self.model.total_queued_drivers += 1
                    if self.reserved_customer:
                        self._set_belt_lane_from_target()
                        self.model.cars_inside += 1
                        self.state = "DRIVING_TO_SPOT"
                    else:
                        self.target_space_id = self.model.get_free_unreserved_space_id()
                        self._set_belt_lane_from_target()
                        self.model.cars_inside += 1
                        self.state = "DRIVING_TO_SPOT"
                    return
                else:
                    # Cannot enter: wait at gate
                    self.waiting_for_gate = True
                    self._start_queueing()
                    self.state = "WAITING_AT_GATE"
                    return

            # Move toward gate
            nx, ny = x + 1, y
            old_pos = self.pos
            self.try_move_to((nx, ny))
            
            # If couldn't move, start queuing
            if self.pos == old_pos:
                self.waiting_for_gate = True
                self._start_queueing()
                self.state = "WAITING_AT_GATE"
            else:
                self.waiting_for_gate = False
            return

        # ---------------- WAITING_AT_GATE ----------------
        if self.state == "WAITING_AT_GATE":
            x, y = self.pos
            gx, gy = self.model.entry_gate_2.pos

            # Car at the gate cell (front of the line): check entry
            if (x, y) == (gx, gy):
                can_enter = False
                if self.reserved_customer:
                    can_enter = True
                else:
                    if self.model.free_unreserved_capacity() > 0:
                        can_enter = True
                
                if can_enter:
                    self._stop_queueing(entered=True)
                    if self.reserved_customer:
                        self._set_belt_lane_from_target()
                        self.model.cars_inside += 1
                        self.waiting_for_gate = False
                        self.state = "DRIVING_TO_SPOT"
                    else:
                        self.target_space_id = self.model.get_free_unreserved_space_id()
                        self._set_belt_lane_from_target()
                        self.model.cars_inside += 1
                        self.waiting_for_gate = False
                        self.state = "DRIVING_TO_SPOT"
                    return
                else:
                    self.waiting_for_gate = True
                    return

            # Try to move right toward the gate
            nx, ny = x + 1, y
            old_pos = self.pos
            self.try_move_to((nx, ny))

            if self.pos == old_pos:
                self.waiting_for_gate = True
                if self.queue_entry_step is None:
                    self._start_queueing()
            else:
                self.waiting_for_gate = False
            return
        
        # ---------------- DRIVING_TO_SPOT ----------------
        if self.state == "DRIVING_TO_SPOT":
            self.drive_to_spot()
            return

        # ---------------- PARKED ----------------
        if self.state == "PARKED":
            self.remaining_time -= 1
            if self.remaining_time <= 0:
                self.state = "EXITING"
            return

        # ---------------- EXITING ----------------
        if self.state == "EXITING":
            self.drive_to_exit()
            return

        # ---------------- EXITED ----------------
        if self.state == "EXITED":
            if self in self.model.scheduler.agents:
                self.model.grid.remove_agent(self)
                self.model.scheduler.remove(self)

    # --- Queueing Helpers ---
    def _start_queueing(self):
        if self.queue_entry_step is None:
            self.queue_entry_step = self.model.current_step

    def _stop_queueing(self, entered: bool):
        if self.queue_entry_step is not None:
            q_time = self.model.current_step - self.queue_entry_step
            self.model.total_queue_time += q_time
            if entered:
                self.model.total_queued_drivers += 1
            self.queue_entry_step = None


    # ---------- Collision + Lane Discipline ----------
    def try_move_to(self, new_pos):
        if self.model.is_parking_cell(new_pos):
            space = None
            if self.target_space_id is not None:
                space = self.model.space_by_id[self.target_space_id]
            allowed = (
                self.state == "DRIVING_TO_SPOT"
                and space is not None
                and new_pos == space.pos
            )
            if not allowed:
                return

        if self.model.cell_has_driver(new_pos):
            return

        self.model.grid.move_agent(self, new_pos)

    # ---------- Movement to Spot ----------
    def drive_to_spot(self):
        space = self.model.space_by_id[self.target_space_id]
        x, y = self.pos
        tx, ty = space.pos

        # already on the bay
        if (x, y) == (tx, ty):
            if not space.occupied:
                space.occupied = True
                space.occupant_id = self.unique_id
                self.current_space_id = space.unique_id
                self.state = "PARKED"
                self.model.parked_count += 1

                if self.reserved_customer and self.reservation is not None:
                    if not self.reservation.get("fulfilled", False):
                        self.reservation["fulfilled"] = True
                        self.model.total_reservations_fulfilled += 1
            return

        lane_y = self.belt_lane_y if self.belt_lane_y is not None else self.model.road_y
        start_x = self.model.parking_start_x
        nx, ny = x, y

        if x <= start_x and y != lane_y:
            ny = y + 1 if y < lane_y else y - 1
            nx = x
        elif y == lane_y and x != tx:
            nx = x + 1 if x < tx else x - 1
            ny = y

            # If next step is the spot, wait if it's not empty.
            if nx == tx:
                 if space.occupied and space.occupant_id != self.unique_id:
                     return
            
            if nx == tx:
                 if space.occupied and space.occupant_id != self.unique_id:
                     # Wait here. Do not block the door.
                     return


            nx = x + 1 if x < tx else x - 1
            ny = y
        elif x == tx and y != ty:
            ny = y + 1 if y < ty else y - 1
            nx = x
        else:
            if x < tx: nx = x + 1
            elif x > tx: nx = x - 1
            elif y < ty: nx = x
            elif y > ty: nx = x - 1 

        self.try_move_to((nx, ny))

        if self.pos == space.pos and not space.occupied:
            space.occupied = True
            space.occupant_id = self.unique_id
            self.current_space_id = space.unique_id
            self.state = "PARKED"
            self.model.parked_count += 1
            
            price_to_pay = self.parking_duration * getattr(self, "agreed_rate", self.model.base_per_minute)
            if getattr(self, "is_reserved", False):
                price_to_pay += self.model.reservation_fee
            self.model.total_revenue += price_to_pay
    
    def _set_belt_lane_from_target(self):
        lane_y = self.model.road_y
        if self.target_space_id is not None:
            sx, sy = self.model.space_by_id[self.target_space_id].pos
            for mid_y in getattr(self.model, "belt_mid_rows", []):
                if abs(sy - mid_y) == 1:
                    lane_y = mid_y
                    break
        self.belt_lane_y = lane_y

    # ---------- Movement to Exit ----------
    def drive_to_exit(self):
        space = None
        if self.target_space_id is not None:
            space = self.model.space_by_id[self.target_space_id]

        prev = self.pos
        x, y = self.pos
        ex, ey = self.model.exit_gate.pos
        road_y = self.model.road_y

        if (x, y) == (ex, ey):
            self.state = "EXITED"
            self.model.cars_inside -= 1
            self.model.grid.remove_agent(self)
            self.model.scheduler.remove(self)
            return

        lane_y = self.belt_lane_y if self.belt_lane_y is not None else road_y
        parking_end_x = getattr(self.model, "parking_end_x", self.model.parking_start_x)
        nx, ny = x, y

        if x <= parking_end_x and y != lane_y:
            ny = y + 1 if y < lane_y else y - 1
            nx = x
        elif x <= parking_end_x and y == lane_y:
            nx = x + 1
            ny = y
        elif x > parking_end_x and y != road_y:
            ny = y + 1 if y < road_y else y - 1
            nx = x
        else:
            if x < ex: nx = x + 1
            elif x > ex: nx = x - 1

        self.try_move_to((nx, ny))

        if space is not None and prev == space.pos and self.pos != space.pos:
            space.occupied = False
            space.occupant_id = None
            self.target_space_id = None

    def force_eviction_of_occupant(self, space_id):
        """Helper to find whoever is in the space and tell them to leave immediately."""
        space = self.model.space_by_id.get(space_id)
        if not space or not space.occupied:
            return
            
        # We need to find the specific driver agent in that cell
        cell_contents = self.model.grid.get_cell_list_contents([space.pos])
        for agent in cell_contents:
            if isinstance(agent, Driver) and agent.unique_id != self.unique_id:
                # Found the squatter.
                if agent.state != "EXITING":
                    agent.remaining_time = 0
                    agent.state = "EXITING"
                    # Instantly vacate the spot
                    space.occupied = False
                    space.occupant_id = None
                    # Move the squatter to the road lane to start exiting (avoid blocking)
                    road_y = self.model.road_y
                    sx, sy = space.pos
                    exit_pos = (sx, road_y)  # Move to road lane at the same x
                    self.model.grid.move_agent(agent, exit_pos)
                    # Note: They will continue exiting from there in their next steps.


class ParkingLotModel(Model):
    def __init__(
        self,
        width,
        height,
        n_spaces,
        arrival_prob=0.7, 
        day_length_steps=1000,
        p_not_enter_long_queue=0.90,
        seed=None,
        reservation_percent=0.0,        
        reservation_hold_time=0.05,       
        parking_strategy="Standard",
    ):
        super().__init__(seed=seed)
        self.grid = MultiGrid(width, height, torus=False)
        self.scheduler = RandomActivation(self)

        self.arrival_prob = arrival_prob
        self.day_length_steps = day_length_steps
        self.p_not_enter_long_queue = p_not_enter_long_queue
        self.reservation_percent = reservation_percent
        self.reservation_hold_time = reservation_hold_time
        self.parking_strategy = parking_strategy
        
        self.base_per_minute = 0.022
        self.reservation_fee = 5.0
        
        self.enable_dynamic_pricing = False
        self.reservation_mode = "none"

        if self.parking_strategy == "Dynamic Pricing":
            self.enable_dynamic_pricing = True 
        elif self.parking_strategy == "Reservations":
            self.reservation_mode = "reservations"

        self.current_per_minute_rate = self.base_per_minute
        self.total_revenue = 0.0
        self.total_price_turnaways = 0

        self.current_step = 0
        self.total_arrivals = 0
        self.total_not_entered_long_queue = 0
        self.total_queue_time = 0
        self.total_queued_drivers = 0
        self.cars_inside = 0
        self.parked_count = 0

        # --- Grid & Gate Setup ---
        self.road_y = height // 2
        self.entry_pos = (0, self.road_y)
        min_width = n_spaces + 7
        if width < min_width:
            raise ValueError(f"Grid width {width} too small.")

        second_entry_x = width - (n_spaces + 6)
        second_entry_pos = (second_entry_x, self.road_y)

        self.entry_gate = Gate(self.next_id(), self, self.entry_pos, "IN")
        self.entry_gate_2 = Gate(self.next_id(), self, second_entry_pos, "IN")
        self.grid.place_agent(self.entry_gate, self.entry_gate.pos)       
        self.grid.place_agent(self.entry_gate_2, second_entry_pos)
        self.scheduler.add(self.entry_gate)
        self.scheduler.add(self.entry_gate_2)

        self.parking_spaces = []
        self.parking_start_x = second_entry_x + 3
        start_x = self.parking_start_x
        self.exit_pos = (self.parking_start_x + n_spaces + 2, self.road_y)
        self.exit_gate = Gate(self.next_id(), self, self.exit_pos, "OUT")
        self.grid.place_agent(self.exit_gate, self.exit_gate.pos)
        self.scheduler.add(self.exit_gate)
        
        belt_offsets = [-6, -3, 0, 3, 6]
        self.belt_mid_rows = []
        parking_rows = []
        for offset in belt_offsets:
            mid_y = self.road_y + offset
            if 0 <= mid_y - 1 < height and 0 <= mid_y + 1 < height:
                self.belt_mid_rows.append(mid_y)
                parking_rows.extend([mid_y - 1, mid_y + 1])

        last_parking_x = start_x
        for row in parking_rows:
            for i in range(n_spaces):
                x = start_x + i
                if x >= width - 1: break
                last_parking_x = x
                pos = (x, row)
                s = ParkingSpace(self.next_id(), self, pos)
                self.parking_spaces.append(s)
                self.grid.place_agent(s, pos)
                self.scheduler.add(s)
        
        self.parking_end_x = last_parking_x
        self.space_by_id = {s.unique_id: s for s in self.parking_spaces}

        # --- Reservations Setup (UPDATED FOR MULTIPLE) ---
        self.reservations = [] 
        self.total_reservations = 0
        self.total_reservations_fulfilled = 0

        if self.reservation_mode == "reservations" and self.reservation_percent > 0:
            # 1. Select the spots that CAN accept reservations (e.g., top 20%)
            sorted_spaces = sorted(self.parking_spaces, key=lambda s: (s.pos[0], s.pos[1]))
            reserve_count = int(round(self.reservation_percent * len(sorted_spaces)))
            reservable_spaces = sorted_spaces[:reserve_count]

            # 2. For each reservable spot, generate sequential non-overlapping reservations
            for s in reservable_spaces:
                s.is_reserved = True  # Just a marker for "VIP Enabled"
                
                # Start planning from step 50
                plan_t = 50
                while plan_t < self.day_length_steps - 100:
                    # Chance to have a reservation here
                    if self.random.random() < 0.6: # 60% chance to book this slot
                        duration = self.random.randint(60, 200)
                        
                        reservation = {
                            "space_id": s.unique_id,
                            "time": plan_t,
                            "duration": duration,
                            "handled": False,
                            "fulfilled": False,
                            "released_at": None,
                        }
                        self.reservations.append(reservation)
                        self.total_reservations += 1
                        
                        # Move time forward: duration + buffer
                        plan_t += duration + self.random.randint(30, 60)
                    else:
                        # Skip some time (public parking allowed during this gap)
                        plan_t += self.random.randint(60, 180)

        self.datacollector = DataCollector(
            model_reporters={
                "OccupiedSpaces": lambda m: sum(1 for s in m.parking_spaces if s.occupied),
                "FreeSpaces": lambda m: sum(1 for s in m.parking_spaces if not s.occupied),
                "NumDrivers": self.get_num_drivers,
                "CarsInside": lambda m: m.cars_inside,
                "CarsWaitingAtGate": lambda m: m.cars_waiting_for_gate(),
                "ReservationsFulfilled": lambda m: m.total_reservations_fulfilled,
            }
        )

    def update_dynamic_price(self):
        if not self.enable_dynamic_pricing:
            self.current_per_minute_rate = self.base_per_minute
            return
        total_spots = len(self.parking_spaces)
        occupied = sum(1 for s in self.parking_spaces if s.occupied)
        occupancy_rate = occupied / total_spots if total_spots > 0 else 0
        if occupancy_rate < 0.50:
            self.current_per_minute_rate = self.base_per_minute * 0.5
        elif occupancy_rate > 0.80:
            self.current_per_minute_rate = self.base_per_minute * 2.0
        else:
            self.current_per_minute_rate = self.base_per_minute

    def cars_waiting_for_gate(self):
        return sum(1 for a in self.scheduler.agents if isinstance(a, Driver) and getattr(a, "waiting_for_gate", False))
    
    def arrival_prob_at_step(self, t: int) -> float:
        tau = t % self.day_length_steps
        frac = tau / self.day_length_steps
        if frac < 0.15: base = 0.10
        elif frac < 0.25: base = 0.20
        elif frac < 0.40: base = 0.50
        elif frac < 0.55: base = 0.70
        elif frac < 0.70: base = 0.40
        elif frac < 0.85: base = 0.20
        else: base = 0.10
        return self.arrival_prob * base

    def is_parking_cell(self, pos):
        return any(s.pos == pos for s in self.parking_spaces)

    def get_num_drivers(self):
        return sum(1 for a in self.scheduler.agents if isinstance(a, Driver))

    def cell_has_driver(self, pos):
        agents = self.grid.get_cell_list_contents([pos])
        return any(isinstance(a, Driver) for a in agents)

    def _reserved_space_ids(self):
        # Only active reservations matter? 
        # Actually, for get_free_unreserved_space_id, we now IGNORE reservations
        # unless they are actively held/occupied.
        reserved = set()
        for a in self.scheduler.agents:
            if isinstance(a, Driver) and a.target_space_id is not None:
                reserved.add(a.target_space_id)
        return reserved

    def get_free_unreserved_space_id(self):
        reserved_targets = self._reserved_space_ids()
        
        # Candidate spots: Not occupied, not targeted by someone else, not 'Held' for no-show
        free = [
            s for s in self.parking_spaces
            if (not s.occupied) 
            and (s.unique_id not in reserved_targets)
        ]
        
        if not free:
            return None
        # Fill strictly from left to right to maximize efficiency
        free.sort(key=lambda s: s.pos[0])
        return free[0].unique_id

    def free_unreserved_capacity(self):
        reserved_targets = self._reserved_space_ids()
        return sum(
            1 for s in self.parking_spaces
            if (not s.occupied) 
            and (s.unique_id not in reserved_targets)
        )
    
    def reserved_space_available_for(self, space_id):
        s = self.space_by_id.get(space_id, None)
        if s is None: return False
        # Available if not occupied (or occupied by self, but we are at gate)
        return not s.occupied

    def process_reservations(self):
        if self.reservation_mode != "reservations":
            return

        for r in self.reservations:
            if r["handled"]:
                continue
            
            # TRIGGER RESERVATION
            if r["time"] == self.current_step:
                s = self.space_by_id[r["space_id"]]
                
                # --- EVICTION LOGIC ---
                # If the spot is currently occupied by a "normal" driver, KICK THEM OUT.
                if s.occupied and s.occupant_id is not None:
                    # Find the driver agent
                    # Since we don't have a direct dict of agents by ID, we search or use occupant_id lookup if we had it.
                    # We'll scan scheduler for safety.
                    occupant_agent = None
                    for agent in self.scheduler.agents:
                        if agent.unique_id == s.occupant_id and isinstance(agent, Driver):
                            occupant_agent = agent
                            break
                    
                    if occupant_agent:
                        # BOOT THEM: Set time to 0 -> State to EXITING next step
                        occupant_agent.remaining_time = 0
                        occupant_agent.state = "EXITING"
                        # Note: Physically they are still there. The VIP might have to wait a moment.

                # Always create VIP (removed no-show chance)
                drv = Driver(self.next_id(), self, reserved=True, reservation=r)
                drv.arrival_step = self.current_step
                drv.agreed_rate = self.current_per_minute_rate
                self.scheduler.add(drv)
                r["handled"] = True

    def maybe_arrive(self):
        if (self.current_step >= self.day_length_steps):
            return

        p = self.arrival_prob_at_step(self.current_step)
        if self.random.random() >= p:
            return

        self.total_arrivals += 1
        # Increase WTP range to make drivers more willing to pay higher rates
        driver_wtp = self.random.uniform(0.02, 0.08)  # Adjusted from (0.01, 0.05)
        self.update_dynamic_price()

        if self.current_per_minute_rate > driver_wtp:
            self.total_price_turnaways += 1
            return
        
        current_queue_len = self.cars_waiting_for_gate()
        if current_queue_len >= 6:  
            if self.random.random() < self.p_not_enter_long_queue + 0.05 * (current_queue_len - 8):
                self.total_not_entered_long_queue += 1
                return

        drv = Driver(self.next_id(), self)
        drv.arrival_step = self.current_step
        drv.agreed_rate = self.current_per_minute_rate
        drv.is_reserved = False
        self.scheduler.add(drv)


    def step(self):
        self.current_step += 1
        self.process_reservations()
        self.maybe_arrive()
        self.scheduler.step()
        self.datacollector.collect(self)

        if self.current_step == self.day_length_steps:
            self.save_data()
            print(f"Day ended. Data saved to 'simulation_results.csv'")

    def save_data(self):
        df = self.datacollector.get_model_vars_dataframe()
        filename = "simulation_results.csv"
        df.to_csv(filename)