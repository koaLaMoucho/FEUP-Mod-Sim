from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import math, random


def parking_duration_steps(rng=random):
    return rng.randint(40, 80)


class ParkingSpace(Agent):
    def __init__(self, unique_id, model, pos):
        super().__init__(unique_id, model)
        self.pos = pos
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

    def __init__(self, unique_id, model, parking_duration=None):
        super().__init__(unique_id, model)
        self.state = "ARRIVING"
        self.waiting_for_gate = False


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
                if self.model.free_unreserved_capacity() > 0:
                    self.target_space_id = self.model.get_free_unreserved_space_id()
                    self.model.cars_inside += 1
                    self.waiting_for_gate = False
                    self.state = "DRIVING_TO_SPOT"
                else:
                    self.waiting_for_gate = True
                    self.state = "WAITING_AT_GATE"
                return

            # Move right toward gate_2 if free
            nx, ny = x + 1, y
            old_pos = self.pos
            self.try_move_to((nx, ny))
            #Se nao conseguir andar pra frente é porque tá a esperar na fila
            if self.pos == old_pos and self.model.free_unreserved_capacity() == 0:
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
                    # leave waiting count
                    

                    self.target_space_id = self.model.get_free_unreserved_space_id()
                    self.model.cars_inside += 1
                    self.waiting_for_gate = False
                    self.state = "DRIVING_TO_SPOT"
                # if still full: just stay on the gate cell
                else:
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

        if (x, y) == (tx, ty):
            if not space.occupied:
                space.occupied = True
                space.occupant_id = self.unique_id
                self.current_space_id = space.unique_id
                self.state = "PARKED"
                self.model.parked_count += 1
            return

        nx, ny = x, y
        if  y < ty:
            ny = y + 1
        elif y > ty:
            ny = y - 1
        elif x < tx:
            nx = x + 1
        elif x > tx:
            nx = x - 1

        prev = self.pos
        self.try_move_to((nx, ny))

        if self.pos == space.pos and not space.occupied:
            space.occupied = True
            space.occupant_id = self.unique_id
            self.current_space_id = space.unique_id
            self.state = "PARKED"
            self.model.parked_count += 1

    # ---------- Movement to exit ----------
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

        if y != road_y:
            ny = road_y
            nx = x
        else:
            nx, ny = x, y
            if x < ex:
                nx = x + 1
            elif x > ex:
                nx = x - 1

        self.try_move_to((nx, ny))

        if space is not None and prev == space.pos and self.pos != space.pos:
            space.occupied = False
            space.occupant_id = None
            self.target_space_id = None


class ParkingLotModel(Model):
    def __init__(self, width, height, n_spaces, arrival_prob, seed=None):
        super().__init__(seed=seed)
        self.grid = MultiGrid(width, height, torus=False)
        self.scheduler = RandomActivation(self)

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
        start_x = width // 2 - n_spaces // 2
        parking_rows = [self.road_y - 1, self.road_y + 1]

        self.parking_spaces = []

        # same horizontal start for all belts
        start_x = width // 2 - n_spaces // 2

        # we create 3 belts of parking:
        # one centered at road_y (current),
        # one above, one below.
        # each belt has two rows: (mid_y - 1) and (mid_y + 1)
        belt_offsets = [-3, 0, 3]  # vertical offsets of each belt's "middle" relative to road_y
        
        parking_rows = []

        for offset in belt_offsets:
            mid_y = self.road_y + offset
            rows_for_belt = [mid_y - 1, mid_y + 1]
            for row in rows_for_belt:
                # keep only rows inside the grid
                if 0 <= row < height:
                    parking_rows.append(row)

        # build spaces on all selected rows, same x-range for all
        for row in parking_rows:
            for i in range(n_spaces):
                x = start_x + i
                if x >= width - 1:
                    break
                pos = (x, row)
                s = ParkingSpace(self.next_id(), self, pos)
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

        drv = Driver(self.next_id(), self)
        self.scheduler.add(drv)

    def step(self):
        self.maybe_arrive()
        self.scheduler.step()
        self.datacollector.collect(self)
