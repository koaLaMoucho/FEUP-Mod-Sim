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
        return rng.randint(15, 45)

    # Normal stay
    if u < 0.75:
        return rng.randint(60, 150)

    # Long stay
    return rng.randint(240, 540)



class ParkingSpace(Agent):
    def __init__(self, unique_id, model, pos):
        super().__init__(unique_id, model)
        self.pos = pos
        self.occupied = False
        self.occupant_id = None

        self.is_reserved = False
        self.held = False
        self.held_until = None

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
        

        self.parking_duration = parking_duration or parking_duration_steps(rng=self.random)
        self.remaining_time = self.parking_duration

        # --- timestamps para KPIs ---
        self.arrival_step = None
        self.queue_entry_step = None

        # --- estado de abandono (balked) ---
        self.balked = False


    def step(self):

        if self.state == "BALKING":
            self._balking_move()
            return

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

            # At gate_2: check if we can enter
            if (x, y) == (gx, gy):
                can_enter = False
                if self.reserved_customer:
                    if self.model.reserved_space_available_for(self.target_space_id):
                        can_enter = True
                else:
                    if self.model.free_unreserved_capacity() > 0:
                        can_enter = True
                
                if can_enter:
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

            # Not at gate_2 yet: always move right toward it (no bypassing)
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
                    if self.model.reserved_space_available_for(self.target_space_id):
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
                    # Still waiting
                    self.waiting_for_gate = True
                    return

            # Non-front cars: can balk probabilistically after threshold
            if self.queue_entry_step is not None:
                waited = self.model.current_step - self.queue_entry_step
                if waited >= self.model.max_wait_time:
                    if self.random.random() < self.model.p_balk_per_step_after_wait:
                        self._balk_and_start_leaving()
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

    def _start_queueing(self):
        """Marcar que o condutor entrou em fila no portão."""
        if self.queue_entry_step is None:
            self.queue_entry_step = self.model.current_step

    def _stop_queueing(self, entered: bool):
        """Parar de contar fila; 'entered=True' só quando o carro entrou no parque."""
        if self.queue_entry_step is not None:
            q_time = self.model.current_step - self.queue_entry_step
            self.model.total_queue_time += q_time
            if entered:
                self.model.total_queued_drivers += 1
            self.queue_entry_step = None


    def _balk_and_start_leaving(self):
        self.balked = True
        # fechar a contagem de tempo de fila, mas sem contar como "queued driver que entrou"
        self._stop_queueing(entered=False)

        self.model.total_turned_away += 1
        self.model.total_balked += 1

        self.waiting_for_gate = False
        self.state = "BALKING"
        self._balked_moved_down = False

    
    def _balking_move(self):
        """
        Movimento visual para quem estava na fila e desistiu (BALKING):
        1) primeiro passo: desce 1 em y
        2) depois: anda para a esquerda até alinhar com entry_pos.x
        3) quando chega ao x do entry, desaparece
        """
        x, y = self.pos
        entry_x, entry_y = self.model.entry_pos

        # primeiro passo após sair da fila: descer 1 em y
        if not getattr(self, "_balked_moved_down", False):
            new_y = y + 1
            if new_y < self.model.grid.height:
                new_pos = (x, new_y)
            else:
                new_pos = (x, y)
            self._balked_moved_down = True
        else:
            # depois, mover para a esquerda até x == entry_x
            if x > entry_x:
                new_x = x - 1
                new_pos = (new_x, y)
            else:
                # já chegou "à entrada mas em y+1": remove o agente
                if self in self.model.scheduler.agents:
                    self.model.grid.remove_agent(self)
                    self.model.scheduler.remove(self)
                return

        # tentar mover (ignoramos colisões de forma simples; se bloquear, removemos)
        try:
            self.model.grid.move_agent(self, new_pos)
        except Exception:
            # se der problema, simplesmente removemos para não estragar a simulação
            if self in self.model.scheduler.agents:
                self.model.grid.remove_agent(self)
                self.model.scheduler.remove(self)



    # ---------- Collision + lane discipline ----------
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

    # ---------- Movement to spot ----------
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

                # if this driver fulfilled a reservation, record KPI
                if self.reserved_customer and self.reservation is not None and not self.reservation.get("fulfilled", False):
                    self.reservation["fulfilled"] = True
                    self.model.total_reservations_fulfilled += 1

            return

        # ---- decide lane for this bay (middle lane of its belt) ----
        lane_y = self.belt_lane_y if self.belt_lane_y is not None else self.model.road_y

        start_x = self.model.parking_start_x

        # ---- movement priority ----
        nx, ny = x, y

        if x <= start_x and y != lane_y:
            # we are before the parking area: go vertically to the belt lane
            ny = y + 1 if y < lane_y else y - 1
            nx = x

        elif y == lane_y and x != tx:
            # on the belt lane: move horizontally to align with the bay
            nx = x + 1 if x < tx else x - 1
            ny = y

        elif x == tx and y != ty:
            # aligned in x and on/near lane: move vertically into the bay row
            ny = y + 1 if y < ty else y - 1
            nx = x

        else:
            # fallback: simple Manhattan toward target (rare edge cases)
            if x < tx:
                nx = x + 1
                ny = y
            elif x > tx:
                nx = x - 1
                ny = y
            elif y < ty:
                nx = x
                ny = y + 1
            elif y > ty:
                nx = x
                ny = y - 1

        prev = self.pos
        self.try_move_to((nx, ny))

        # if after moving we are actually on our bay, park atomically
        if self.pos == space.pos and not space.occupied:
            space.occupied = True
            space.occupant_id = self.unique_id
            self.current_space_id = space.unique_id
            self.state = "PARKED"
            self.model.parked_count += 1
            
            # --- Collect Revenue ---
            price_to_pay = self.parking_duration * getattr(self, "agreed_rate", self.model.base_per_minute)
            if getattr(self, "is_reserved", False):
                price_to_pay += self.model.reservation_fee
            self.model.total_revenue += price_to_pay
    
    
    def _set_belt_lane_from_target(self):
        """
        Decide which belt lane (middle row of the belt) this car belongs to,
        based on the target parking space.
        """
        lane_y = self.model.road_y
        if self.target_space_id is not None:
            sx, sy = self.model.space_by_id[self.target_space_id].pos
            for mid_y in getattr(self.model, "belt_mid_rows", []):
                if abs(sy - mid_y) == 1:
                    lane_y = mid_y
                    break
        self.belt_lane_y = lane_y


    # ---------- Movement to exit ----------
    def drive_to_exit(self):
        # identify the space we are leaving (for freeing)
        space = None
        if self.target_space_id is not None:
            space = self.model.space_by_id[self.target_space_id]

        prev = self.pos
        x, y = self.pos
        ex, ey = self.model.exit_gate.pos
        road_y = self.model.road_y

        # reached exit: leave the system
        if (x, y) == (ex, ey):
            self.state = "EXITED"
            self.model.cars_inside -= 1
            self.model.grid.remove_agent(self)
            self.model.scheduler.remove(self)
            return

        # ---- lane for this car's belt ----
        lane_y = self.belt_lane_y if self.belt_lane_y is not None else road_y

        parking_end_x = getattr(self.model, "parking_end_x", self.model.parking_start_x)

        # ---- movement priority (reverse of entry) ----
        nx, ny = x, y

        if x <= parking_end_x and y != lane_y:
            # still inside the parking columns: go vertically to the belt lane
            ny = y + 1 if y < lane_y else y - 1
            nx = x

        elif x <= parking_end_x and y == lane_y:
            # on the belt lane inside parking area: move right out of the bays
            nx = x + 1
            ny = y

        elif x > parking_end_x and y != road_y:
            # to the right of parking: drop to main road (no bays here)
            ny = y + 1 if y < road_y else y - 1
            nx = x

        else:
            # on main road to the right of parking: go horizontally to exit
            nx, ny = x, y
            if x < ex:
                nx = x + 1
            elif x > ex:
                nx = x - 1

        # move with collision + no-drive-through-bays logic
        self.try_move_to((nx, ny))

        # after moving: if we just left the parking space cell, free it now
        if space is not None and prev == space.pos and self.pos != space.pos:
            space.occupied = False
            space.occupant_id = None
            self.target_space_id = None




class ParkingLotModel(Model):
    def __init__(
        self,
        width,
        height,
        n_spaces,
        arrival_prob=0.7,
        max_queue_length=10,
        max_wait_time=15,   
        day_length_steps=1000,
        p_not_enter_long_queue=0.80,
        p_balk_per_step_after_wait=0.10,
        seed=None,
        reservation_percent=0.0,        # fraction of spots to reserve (0..1)
        reservation_hold_time=30,       # steps to hold a spot after a no-show
        reservation_no_show_prob=0.1,   # prob that a reservation is a no-show
        parking_strategy="Standard",
    ):
        super().__init__(seed=seed)
        self.grid = MultiGrid(width, height, torus=False)
        self.scheduler = RandomActivation(self)

        self.arrival_prob = arrival_prob
        self.day_length_steps = day_length_steps
        self.p_not_enter_long_queue = p_not_enter_long_queue
        self.p_balk_per_step_after_wait = p_balk_per_step_after_wait

        self.reservation_percent = reservation_percent
        self.reservation_hold_time = reservation_hold_time
        self.reservation_no_show_prob = reservation_no_show_prob

        self.parking_strategy = parking_strategy
        self.base_per_minute = 0.022  # euros per minute
        self.reservation_fee = 5.0  # euros
        
        self.enable_dynamic_pricing = False
        self.reservation_mode = "none"

        if self.parking_strategy == "Dynamic Pricing":
            self.enable_dynamic_pricing = True
            
        elif self.parking_strategy == "Reservations":
            self.reservation_mode = "reservations"

        #-- dynamic pricing ---
        self.current_per_minute_rate = self.base_per_minute
        self.total_revenue = 0.0
        self.total_price_turnaways = 0


        # --- parâmetros de comportamento na fila ---
        self.max_queue_length = max_queue_length      # L: comprimento máximo da fila aceitável
        self.max_wait_time = max_wait_time            # T: tempo máximo em fila (steps)

        # --- time and KPI counters ---
        self.current_step = 0

        self.total_arrivals = 0

        # turned-away total (qualquer motivo)
        self.total_turned_away = 0

        # 1) viu fila grande e nem entrou
        self.total_not_entered_long_queue = 0

        # 2) já estava na fila e desistiu (balked)
        self.total_balked = 0

        self.total_queue_time = 0
        self.total_queued_drivers = 0

        self.total_revenue = 0.0

        self.cars_inside = 0
        self.parked_count = 0


        ##positions

        self.road_y = height // 2

        self.entry_pos = (0, self.road_y)

        min_width = n_spaces + 7  # 1 (entry) + 1 (second_entry) + 2 + n_spaces + 2 + 1 (exit)
        if width < min_width:
            raise ValueError(
                f"Grid width {width} too small for {n_spaces} spaces; need at least {min_width}"
            )


        second_entry_x = width - (n_spaces + 6)
        second_entry_pos = (second_entry_x, self.road_y)

        self.entry_gate = Gate(self.next_id(), self, self.entry_pos, "IN")
        self.entry_gate_2 = Gate(self.next_id(), self, second_entry_pos, "IN")
        self.grid.place_agent(self.entry_gate, self.entry_gate.pos)       
        self.grid.place_agent(self.entry_gate_2, second_entry_pos)
        self.scheduler.add(self.entry_gate)
        self.scheduler.add(self.entry_gate_2)

       

        
        

        self.parking_spaces = []

        # same horizontal start for all belts
        
        self.parking_start_x = second_entry_x + 3  # gate2 + 2 empty + 1st parking column
        start_x = self.parking_start_x

        
        self.exit_pos = (self.parking_start_x + n_spaces + 2, self.road_y)
        
        self.exit_gate = Gate(self.next_id(), self, self.exit_pos, "OUT")
        
        self.grid.place_agent(self.exit_gate, self.exit_gate.pos)
        
        self.scheduler.add(self.exit_gate)
        
        # middle rows of each belt (one above, one middle, one below)
        belt_offsets = [-6, -3, 0, 3, 6]
        self.belt_mid_rows = []
        parking_rows = []

        for offset in belt_offsets:
            mid_y = self.road_y + offset
            # keep only belts fully inside the grid
            if 0 <= mid_y - 1 < height and 0 <= mid_y + 1 < height:
                self.belt_mid_rows.append(mid_y)
                rows_for_belt = [mid_y - 1, mid_y + 1]
                parking_rows.extend(rows_for_belt)

        # build spaces on all selected rows, same x-range for all
        last_parking_x = start_x
        for row in parking_rows:
            for i in range(n_spaces):
                x = start_x + i
                if x >= width - 1:
                    break
                last_parking_x = x
                pos = (x, row)
                s = ParkingSpace(self.next_id(), self, pos)
                self.parking_spaces.append(s)
                self.grid.place_agent(s, pos)
                self.scheduler.add(s)
        
        self.parking_end_x = last_parking_x

        self.space_by_id = {s.unique_id: s for s in self.parking_spaces}

        # --- reservation scheduling (simple single reservation per reserved spot) ---
        self.reservations = [] 
        self.total_reservations = 0
        self.total_reservations_fulfilled = 0
        self.total_reservations_released = 0

        if self.reservation_mode == "reservations" and self.reservation_percent > 0:
            # pick R% of spaces (leftmost-first for determinism)
            sorted_spaces = sorted(self.parking_spaces, key=lambda s: (s.pos[0], s.pos[1]))
            reserve_count = int(round(self.reservation_percent * len(sorted_spaces)))
            reserved_spaces = sorted_spaces[:reserve_count]
            for s in reserved_spaces:
                s.is_reserved = True
                s.held = False
                s.held_until = None

                # schedule a single reservation time (simple model)
                t = self.random.randrange(self.day_length_steps)
                reservation = {
                    "space_id": s.unique_id,
                    "time": t,
                    "handled": False,
                    "fulfilled": False,
                    "released_at": None,
                }
                self.reservations.append(reservation)
                self.total_reservations += 1


        self.datacollector = DataCollector(
            model_reporters={
                "OccupiedSpaces": lambda m: sum(1 for s in m.parking_spaces if s.occupied),
                "FreeSpaces": lambda m: sum(1 for s in m.parking_spaces if not s.occupied),
                "NumDrivers": self.get_num_drivers,
                "ParkedCount": lambda m: m.parked_count,
                "CarsInside": lambda m: m.cars_inside,
                "CarsWaitingAtGate": lambda m: m.cars_waiting_for_gate(),

                # --- novos KPIs agregados ---
                "TotalArrivals": lambda m: m.total_arrivals,
                "TurnedAway": lambda m: m.total_turned_away,
                "TotalQueueTime": lambda m: m.total_queue_time,
                "TotalQueuedDrivers": lambda m: m.total_queued_drivers,
                "AvgQueueTimeSoFar": lambda m: (
                    m.total_queue_time / m.total_queued_drivers
                    if m.total_queued_drivers > 0 else 0
                ),
                #Helper
                "ArrivalProb": lambda m: m.arrival_prob_at_step(m.current_step),

                "TotalReservations": lambda m: m.total_reservations,
                "ReservationsFulfilled": lambda m: m.total_reservations_fulfilled,
                "ReservationsReleased": lambda m: m.total_reservations_released,
                "ReservedIdleSpaces": lambda m: sum(
                    1 for s in m.parking_spaces if getattr(s, "is_reserved", False) and not s.occupied and not getattr(s, "held", False)
                ),

            }
        )

    def update_dynamic_price(self):
        """
        Adjust price based on occupancy rate.
        < 50% occupied: Discount
        50% - 80% occupied: Base Price
        > 80% occupied: Surge Price
        """
        if not self.enable_dynamic_pricing:
            self.current_per_minute_rate = self.base_per_minute
            return

        total_spots = len(self.parking_spaces)
        occupied = sum(1 for s in self.parking_spaces if s.occupied)
        occupancy_rate = occupied / total_spots if total_spots > 0 else 0

        if occupancy_rate < 0.50:
            self.current_per_minute_rate = self.base_per_minute * 0.5  # 50% off
        elif occupancy_rate > 0.80:
            self.current_per_minute_rate = self.base_per_minute * 2.0  # Surge pricing
        else:
            self.current_per_minute_rate = self.base_per_minute

    

    def cars_waiting_for_gate(self):
        return sum(
            1
            for a in self.scheduler.agents
            if isinstance(a, Driver) and getattr(a, "waiting_for_gate", False)
        )
    
    def arrival_prob_at_step(self, t: int) -> float:
        """
        Time-varying arrival probability (per step), repeating every 'day_length_steps'.
        'arrival_prob' acts as a scaling factor.
        """
        tau = t % self.day_length_steps
        frac = tau / self.day_length_steps

        # base profile (0..1 range), then scaled by self.arrival_prob
        if frac < 0.15:
            base = 0.10   # very early low
        elif frac < 0.25:
            base = 0.20   # early low
        elif frac < 0.40:
            base = 0.50   # ramping up
        elif frac < 0.55:
            base = 0.70   # peak
        elif frac < 0.70:
            base = 0.40   # 
        elif frac < 0.85:
            base = 0.20   # ramping down
        else:
            base = 0.10   # late low

        p = self.arrival_prob * base

        # clamp to [0, 1]
        if p < 0.0:
            return 0.0
        if p > 1.0:
            return 1.0
        return p



    def is_parking_cell(self, pos):
        return any(s.pos == pos for s in self.parking_spaces)

    def get_num_drivers(self):
        return sum(1 for a in self.scheduler.agents if isinstance(a, Driver))

    def cell_has_driver(self, pos):
        agents = self.grid.get_cell_list_contents([pos])
        return any(isinstance(a, Driver) for a in agents)

    def _reserved_space_ids(self):
        reserved = set()
        for a in self.scheduler.agents:
            if isinstance(a, Driver) and a.target_space_id is not None:
                reserved.add(a.target_space_id)
        return reserved

    def get_free_unreserved_space_id(self):
        reserved = self._reserved_space_ids()
        free = [
            s for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved) and (not s.is_reserved)
        ]
        if not free:
            return None
        free.sort(key=lambda s: s.pos[0])
        return free[0].unique_id

    def free_unreserved_capacity(self):
        reserved = self._reserved_space_ids()
        return sum(
            1 for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved) and (not s.is_reserved)
        )
    
    def reserved_space_available_for(self, space_id):
        """Return True if the reserved space exists and is free (not occupied)."""
        s = self.space_by_id.get(space_id, None)
        if s is None:
            return False
        # If occupied -> unavailable. If held but driver is the reserved one, driver will be created tied to reservation.
        return not s.occupied


    def process_reservations(self):
        if self.reservation_mode != "reservations":
            return

        for r in self.reservations:
            if r["handled"]:
                continue
            if r["time"] == self.current_step:
                s = self.space_by_id[r["space_id"]]
                if self.random.random() < (1 - self.reservation_no_show_prob):
                    
                    # Create the VIP Driver
                    drv = Driver(self.next_id(), self, reserved=True, reservation=r)
                    drv.arrival_step = self.current_step
                    
                    # Set agreed rate for reserved drivers
                    drv.agreed_rate = self.current_per_minute_rate
                    drv.is_reserved = True
                    
                    self.scheduler.add(drv)
                    r["handled"] = True
                else:
                    # (No-show logic remains the same)
                    s.held = True
                    s.held_until = self.current_step + self.reservation_hold_time
                    r["handled"] = True
                    r["released_at"] = s.held_until

        # release holds whose time expired
        for s in self.parking_spaces:
            if getattr(s, "held", False) and s.held_until is not None and self.current_step >= s.held_until:
                s.held = False
                s.held_until = None
                self.total_reservations_released += 1

    def maybe_arrive(self):
        p = self.arrival_prob_at_step(self.current_step)
        if self.random.random() >= p:
            return

        # houve uma tentativa de chegada neste tick
        self.total_arrivals += 1

        # Generate a random Willingness To Pay (WTP) for this potential driver (per minute in euros)
        driver_wtp = self.random.uniform(0.01, 0.05)

        # Update the sign rate before they look at it
        self.update_dynamic_price()

        if self.current_per_minute_rate > driver_wtp:
            self.total_turned_away += 1
            self.total_price_turnaways += 1
            return  # Driver leaves immediately due to price

        # comprimento atual da fila (condutores com waiting_for_gate == True)
        current_queue_len = self.cars_waiting_for_gate()

        # --- NOT ENTERING: fila demasiado longa, condutor nem entra ---
        if current_queue_len >= self.max_queue_length:
            # Probabilistic not-entering once queue is too long
            if self.random.random() < self.p_not_enter_long_queue + self.cars_waiting_for_gate() * 0.01:
                self.total_turned_away += 1
                self.total_not_entered_long_queue += 1
                return

        # caso contrário, o carro entra mesmo no sistema (walk-in)
        drv = Driver(self.next_id(), self)
        drv.arrival_step = self.current_step
        drv.agreed_rate = self.current_per_minute_rate
        drv.is_reserved = False
        self.scheduler.add(drv)


    def step(self):
        # avançar o relógio do modelo
        self.current_step += 1

        # process scheduled reservations first (may create reserved drivers / holds)
        self.process_reservations()

        # tentar gerar nova chegada
        self.maybe_arrive()

        # atualizar todos os agentes
        self.scheduler.step()

        # recolher dados
        self.datacollector.collect(self)


        if self.current_step == self.day_length_steps:
            self.save_data()
            print(f"Day ended. Data saved to 'simulation_results.csv'")

    def save_data(self):
        """
        Exports the collected data to a CSV file for analysis in Excel/Pandas.
        """
        # Get the dataframe from the datacollector
        df = self.datacollector.get_model_vars_dataframe()
        
        # Save to CSV
        filename = "simulation_results.csv"
        df.to_csv(filename)
        


