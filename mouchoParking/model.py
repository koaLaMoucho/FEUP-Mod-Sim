from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import math, random



def parking_duration_steps(rng=random):
    return rng.randint(70, 300)


class ParkingSpace(Agent):
    def __init__(self, unique_id, model, pos, space_type="GENERAL"):
        super().__init__(unique_id, model)
        self.pos = pos
        self.space_type = space_type
        self.occupied = False
        self.occupant_id = None

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
    """
    States:
      ARRIVING -> APPROACHING_GATE -> WAITING_AT_GATE
      -> DRIVING_TO_SPOT -> PARKED -> EXITING -> EXITED
    """

    def __init__(self, unique_id, model, driver_type="GENERAL", parking_duration=None):
        super().__init__(unique_id, model)
        self.state = "ARRIVING"
        self.waiting_for_gate = False
        self.belt_lane_y = None

        self.driver_type = driver_type
        self.color = "#%06x" % self.random.randrange(0, 0xFFFFFF)

        self.target_space_id = None
        self.current_space_id = None

        self.parking_duration = parking_duration or parking_duration_steps(rng=self.random)
        self.remaining_time = self.parking_duration

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

            # At gate_2
            if (x, y) == (gx, gy):
                target_id = self.model.find_free_space_for(self.driver_type) 
                if target_id is not None:
                    self.target_space_id = target_id
                    self._set_belt_lane_from_target()
                    self.model.cars_inside += 1
                    self.waiting_for_gate = False
                    self.state = "DRIVING_TO_SPOT"
                else:
                    self.waiting_for_gate = True
                return

            # Move right toward gate_2 if free
            nx, ny = x + 1, y
            old_pos = self.pos
            self.try_move_to((nx, ny))
            #Se nao conseguir andar pra frente é porque tá a esperar na fila
            if self.pos == old_pos and self.model.find_free_space_for(self.driver_type) is None:
                self.waiting_for_gate = True
            else:
                self.waiting_for_gate = False
            return

        # ---------------- WAITING_AT_GATE ----------------
        if self.state == "WAITING_AT_GATE":
            
            x, y = self.pos
            gx, gy = self.model.entry_gate_2.pos

            # car at the gate cell
            if (x, y) == (gx, gy):
                if self.model.free_unreserved_capacity() > 0:
                    # ficou espaço -> entra imediatamente
                    target_id = self.model.find_free_space_for(self.driver_type)
                    self._set_belt_lane_from_target()
                    self.model.cars_inside += 1
                    self.waiting_for_gate = False
                    self.state = "DRIVING_TO_SPOT"
                else:
                    # parque continua cheio -> continua a esperar
                    self.waiting_for_gate = True
                return

            # carros atrás do portão tentam aproximar-se (andar para a direita)
            nx, ny = x + 1, y
            old_pos = self.pos
            self.try_move_to((nx, ny))

            # se não se mexeu e o parque está cheio, está (ou permanece) em fila para o portão
            if self.pos == old_pos and self.model.free_unreserved_capacity() == 0:
                self.waiting_for_gate = True
            else:
                self.waiting_for_gate = False




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
            return

        # ---- decide lane for this bay (middle lane of its belt) ----
        lane_y = self.belt_lane_y if self.belt_lane_y is not None else self.model.roa

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
    def __init__(self, width, height, n_spaces, arrival_prob, n_ev=0, n_pmr=0, seed=None):
        super().__init__(seed=seed)
        self.width = width
        self.height = height
        self.grid = MultiGrid(width, height, torus=False)
        self.scheduler = RandomActivation(self)

        self.n_spaces = n_spaces

        self.n_ev = n_ev
        self.n_pmr = n_pmr
        #self.n_gen = max(0, n_spaces - n_ev - n_pmr)


        self.arrival_prob = arrival_prob
        self.cars_inside = 0
        self.parked_count = 0

        self.road_y = height // 2
        self.entry_pos = (0, self.road_y)
        second_entry_x = self.entry_pos[0] + width // 4
        second_entry_pos = (second_entry_x, self.road_y)
        self.exit_pos = (second_entry_x + n_spaces + 5, self.road_y)


        self.entry_gate = Gate(self.next_id(), self, self.entry_pos, "IN")
        self.entry_gate_2 = Gate(self.next_id(), self, second_entry_pos, "IN")
        self.exit_gate = Gate(self.next_id(), self, self.exit_pos, "OUT")
        self.grid.place_agent(self.entry_gate, self.entry_gate.pos)       
        self.grid.place_agent(self.entry_gate_2, second_entry_pos)
        self.grid.place_agent(self.exit_gate, self.exit_gate.pos)
        self.scheduler.add(self.entry_gate)
        self.scheduler.add(self.entry_gate_2)
        self.scheduler.add(self.exit_gate)

        self.parking_spaces = []
        self.parking_start_x = width // 2 - n_spaces // 2  # used by drivers for path planning
        belt_offsets = [-6, -3, 0, 3, 6]         # middle rows of each belt (one above, one middle, one below)
        self.belt_mid_rows = []
        parking_rows = []
        
        for offset in belt_offsets:
            mid_y = self.road_y + offset
            if 0 <= mid_y - 1 < height and 0 <= mid_y + 1 < height:
                self.belt_mid_rows.append(mid_y)
                parking_rows.extend([mid_y - 1, mid_y + 1])


        # build spaces on all selected rows, same x-range for all
        parking_positions = []
        last_parking_x = self.parking_start_x
        for row in parking_rows:
            for i in range(n_spaces):
                x = self.parking_start_x + i
                if x >= width - 1:
                    break
                last_parking_x = x
                parking_positions.append((x, row))
        self.parking_end_x = last_parking_x


        total_positions = len(parking_positions)
        pmr_to_place = min(self.n_pmr, total_positions)
        ev_to_place = min(self.n_ev, max(0, total_positions - pmr_to_place))

        sorted_positions = sorted(
            parking_positions, key=lambda p: (p[0], abs(p[1] - self.road_y))
        )

        pmr_positions = set(sorted_positions[:pmr_to_place])
        ev_positions = set(sorted_positions[pmr_to_place: pmr_to_place + ev_to_place])

        for pos in parking_positions:
            if pos in pmr_positions:
                stype = "PMR"
            elif pos in ev_positions:
                stype = "EV"
            else:
                stype = "GENERAL"
            s = ParkingSpace(self.next_id(), self, pos, space_type=stype)
            self.parking_spaces.append(s)
            self.grid.place_agent(s, pos)
            self.scheduler.add(s)

        self.space_by_id = {s.unique_id: s for s in self.parking_spaces}

        self.datacollector = DataCollector(
            model_reporters={
                "OccupiedSpaces": lambda m: sum(1 for s in m.parking_spaces if s.occupied),
                "FreeSpaces": lambda m: sum(1 for s in m.parking_spaces if not s.occupied),
                "NumDrivers": self.get_num_drivers,
                "ParkedCount": lambda m: m.parked_count,
                "CarsInside": lambda m: m.cars_inside,
                "CarsWaitingAtGate": lambda m: m.cars_waiting_for_gate(),

            }
        )

        self.datacollector.collect(self)

    def cars_waiting_for_gate(self):
        return sum(
            1
            for a in self.scheduler.agents
            if isinstance(a, Driver) and getattr(a, "waiting_for_gate", False)
        )

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
            if (not s.occupied) and (s.unique_id not in reserved)
        ]
        if not free:
            return None
        free.sort(key=lambda s: s.pos[0])
        return free[0].unique_id

    def free_unreserved_capacity(self):
        reserved = self._reserved_space_ids()
        return sum(
            1 for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved)
        )

    def maybe_arrive(self):
        if self.random.random() >= self.arrival_prob:
            return

        if self.cell_has_driver(self.entry_pos):
            return
        
        reserved = self._reserved_space_ids()
        free_gen = sum(
            1 for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved) and s.space_type == "GENERAL"
        )
        free_ev = sum(
            1 for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved) and s.space_type == "EV"
        )
        free_pmr = sum(
            1 for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved) and s.space_type == "PMR"
        )

        # Choose driver type: weight by available spaces
        total_free = free_gen + free_ev + free_pmr
        if total_free == 0:
            return  # no space available

        rand = self.random.random()
        if rand < free_gen / total_free:
            driver_type = "GENERAL"
        elif rand < (free_gen + free_ev) / total_free:
            driver_type = "EV"
        else:
            driver_type = "PMR"

        drv = Driver(self.next_id(), self, driver_type=driver_type)
        self.scheduler.add(drv)

    def step(self):
        self.maybe_arrive()
        self.scheduler.step()
        self.datacollector.collect(self)

    def find_free_space_for(self, driver_type):
        reserved = self._reserved_space_ids()
        if driver_type == "EV":
            # try EV first
            matching = [
                s for s in self.parking_spaces
                if (not s.occupied) 
                and (s.unique_id not in reserved)
                and (s.space_type == "EV")
            ]
            if matching:
                matching.sort(key=lambda s: s.pos[0])
                return matching[0].unique_id
            # fallback to GENERAL
            matching = [
                s for s in self.parking_spaces
                if (not s.occupied) 
                and (s.unique_id not in reserved)
                and (s.space_type == "GENERAL")
            ]
            if matching:
                matching.sort(key=lambda s: s.pos[0])
                return matching[0].unique_id
            return None

        elif driver_type == "PMR":
            # try PMR first
            matching = [
                s for s in self.parking_spaces
                if (not s.occupied) 
                and (s.unique_id not in reserved)
                and (s.space_type == "PMR")
            ]
            if matching:
                matching.sort(key=lambda s: s.pos[0])
                return matching[0].unique_id
            # fallback to GENERAL
            matching = [
                s for s in self.parking_spaces
                if (not s.occupied) 
                and (s.unique_id not in reserved)
                and (s.space_type == "GENERAL")
            ]
            if matching:
                matching.sort(key=lambda s: s.pos[0])
                return matching[0].unique_id
            return None

        else:  # GENERAL
            # GENERAL drivers use GENERAL spots only
            matching = [
                s for s in self.parking_spaces
                if (not s.occupied) 
                and (s.unique_id not in reserved)
                and (s.space_type == "GENERAL")
            ]
            if matching:
                matching.sort(key=lambda s: s.pos[0])
                return matching[0].unique_id
            return None
    
    def get_free_unreserved_space_id(self):
        reserved = self._reserved_space_ids()
        free = [
            s for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved)
        ]
        if not free:
            return None
        free.sort(key=lambda s: s.pos[0])
        return free[0].unique_id

