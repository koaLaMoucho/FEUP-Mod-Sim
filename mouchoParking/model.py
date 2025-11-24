from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import math, random


def parking_duration_steps(rng=random):
    """Parking duration in discrete steps (small and bounded)."""
    return rng.randint(20, 50)  # between 3 and 7 steps



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
        self.kind = kind  # "IN" or "OUT"

    def step(self):
        pass


class Driver(Agent):
    """
    Single driver type, private parking lot.
    States:
      ARRIVING -> DRIVING_TO_SPOT -> PARKED -> EXITING -> EXITED
    """

    def __init__(self, unique_id, model, parking_duration=None):
        super().__init__(unique_id, model)
        self.state = "ARRIVING"

        # reservation (which space I'm heading to)
        self.target_space_id = None
        # actual occupied space while parked (None otherwise)
        self.current_space_id = None

        self.parking_duration = parking_duration or parking_duration_steps(rng=self.random)
        self.remaining_time = self.parking_duration

    def step(self):
        if self.state == "ARRIVING":
            # place at entry gate
            entry_pos = self.model.entry_gate.pos
            self.model.grid.place_agent(self, entry_pos)

            # choose a free & unreserved space (private lot)
            self.target_space_id = self.model.get_free_unreserved_space_id()
            if self.target_space_id is None:
                # safety guard, should not happen with arrival logic
                self.state = "EXITED"
                self.model.grid.remove_agent(self)
                self.model.scheduler.remove(self)
                return

            self.state = "DRIVING_TO_SPOT"
            return

        if self.state == "DRIVING_TO_SPOT":
            self.drive_to_spot()
            return

        if self.state == "PARKED":
            self.remaining_time -= 1
            if self.remaining_time <= 0:
                # finished parking; start exiting
                self.state = "EXITING"
            return

        if self.state == "EXITING":
            self.drive_to_exit()
            return

        if self.state == "EXITED":
            if self in self.model.scheduler.agents:
                self.model.grid.remove_agent(self)
                self.model.scheduler.remove(self)

    # ---------- Collision + lane discipline ----------

    def try_move_to(self, new_pos):
        """
        Move only if:
        - there is no other Driver in the target cell, and
        - the cell is not a parking space,
          unless it is *this driver's own reserved space* and the driver is going to park.
        """
        # forbid driving onto parking spots unless it's your own target bay and you're heading to park
        if self.model.is_parking_cell(new_pos):
            space = None
            if self.target_space_id is not None:
                space = self.model.space_by_id[self.target_space_id]
            allowed_to_enter = (
                self.state == "DRIVING_TO_SPOT"
                and space is not None
                and new_pos == space.pos
            )
            if not allowed_to_enter:
                return  # cannot drive over other bays

        # collision check
        if self.model.cell_has_driver(new_pos):
            return

        self.model.grid.move_agent(self, new_pos)

    # ---------- Movement to spot ----------

    def drive_to_spot(self):
        space = self.model.space_by_id[self.target_space_id]
        x, y = self.pos
        tx, ty = space.pos

        # already exactly on the bay cell → ensure it's marked occupied and stay parked
        if (x, y) == (tx, ty):
            if not space.occupied:
                space.occupied = True
                space.occupant_id = self.unique_id
                self.current_space_id = space.unique_id
                self.state = "PARKED"
                self.model.parked_count += 1
            return

        # compute next step towards target (Manhattan)
        nx, ny = x, y
        if x < tx:
            nx, ny = x + 1, y
        elif x > tx:
            nx, ny = x - 1, y
        elif y < ty:
            nx, ny = x, y + 1
        elif y > ty:
            nx, ny = x, y - 1

        prev_pos = self.pos
        self.try_move_to((nx, ny))

        # if after the move we are actually on our own bay, park atomically
        if self.pos == space.pos and not space.occupied:
            space.occupied = True
            space.occupant_id = self.unique_id
            self.current_space_id = space.unique_id
            self.state = "PARKED"
            self.model.parked_count += 1

    # ---------- Movement to exit ----------

    def drive_to_exit(self):
        # if we still have a target_space_id, we may need to free it AFTER we move
        space = None
        if self.target_space_id is not None:
            space = self.model.space_by_id[self.target_space_id]

        prev_pos = self.pos  # remember where we were before moving

        x, y = self.pos
        ex, ey = self.model.exit_gate.pos
        road_y = self.model.entry_pos[1]  # row of the road / gates

        # reached exit
        if (x, y) == (ex, ey):
            self.state = "EXITED"
            self.model.grid.remove_agent(self)
            self.model.scheduler.remove(self)
            return

        # decide next step:
        # 1) if not on road row, move vertically towards road row
        if y != road_y:
            if y > road_y:
                nx, ny = x, y - 1  # bay is below road, go up
            else:
                nx, ny = x, y + 1  # bay is above road (if you ever change layout)
        else:
            # 2) already on road row: move horizontally towards exit
            nx, ny = x, y
            if x < ex:
                nx, ny = x + 1, y
            elif x > ex:
                nx, ny = x - 1, y
            elif y < ey:
                nx, ny = x, y + 1
            elif y > ey:
                nx, ny = x, y - 1

        # move with collision + lane-discipline check
        self.try_move_to((nx, ny))

        # after moving: if we just left the parking space cell, free it now
        if space is not None and prev_pos == space.pos and self.pos != space.pos:
            space.occupied = False
            space.occupant_id = None
            self.target_space_id = None




class ParkingLotModel(Model):
    """
    Minimal private parking lot:
    - Small grid
    - Single gate in, single gate out
    - Two rows of parking (top and bottom), each with n_spaces
    """

    def __init__(
        self,
        width,
        height,
        n_spaces,       # spaces per row (top and bottom)
        arrival_prob,
        max_cars,
        seed=None,
    ):
        super().__init__(seed=seed)
        self.grid = MultiGrid(width, height, torus=False)
        self.scheduler = RandomActivation(self)

        self.arrival_prob = arrival_prob
        self.max_cars = max_cars

        # KPIs
        self.parked_count = 0

        # ----- LAYOUT -----
        # road row in the middle
        self.road_y = height // 2

        # entry and exit on the road row
        self.entry_pos = (0, self.road_y)
        self.exit_pos  = (width - 1, self.road_y)

        # Gates
        self.entry_gate = Gate(self.next_id(), self, self.entry_pos, "IN")
        self.exit_gate  = Gate(self.next_id(), self, self.exit_pos, "OUT")
        self.grid.place_agent(self.entry_gate, self.entry_gate.pos)
        self.grid.place_agent(self.exit_gate, self.exit_gate.pos)
        self.scheduler.add(self.entry_gate)
        self.scheduler.add(self.exit_gate)

        # Parking spaces:
        #   one row above the road (self.road_y - 1)
        #   one row below the road (self.road_y + 1)
        self.parking_spaces = []
        start_x = 2  # first column with parking, leave space after entry
        parking_rows = [self.road_y - 1, self.road_y + 1]

        for row in parking_rows:
            for i in range(n_spaces):
                x = start_x + i
                # don't overwrite the exit column
                if x >= width - 1:
                    break
                pos = (x, row)
                s = ParkingSpace(self.next_id(), self, pos)
                self.parking_spaces.append(s)
                self.grid.place_agent(s, pos)
                self.scheduler.add(s)

        # lookup
        self.space_by_id = {s.unique_id: s for s in self.parking_spaces}

        # DataCollector
        self.datacollector = DataCollector(
            model_reporters={
                "OccupiedSpaces": lambda m: sum(1 for s in m.parking_spaces if s.occupied),
                "FreeSpaces":     lambda m: sum(1 for s in m.parking_spaces if not s.occupied),
                "NumDrivers":     self.get_num_drivers,
                "ParkedCount":    lambda m: m.parked_count,
            }
        )


    # ---------- Helpers ----------
    def is_parking_cell(self, pos):
        return any(s.pos == pos for s in self.parking_spaces)


    def get_num_drivers(self):
        return sum(1 for a in self.scheduler.agents if isinstance(a, Driver))

    def cell_has_driver(self, pos):
        agents = self.grid.get_cell_list_contents([pos])
        return any(isinstance(a, Driver) for a in agents)

    def _reserved_space_ids(self):
        """Spaces already targeted by drivers."""
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
        free.sort(key=lambda s: s.pos[0])  # closest to entry
        return free[0].unique_id

    def free_unreserved_capacity(self):
        reserved = self._reserved_space_ids()
        return sum(
            1 for s in self.parking_spaces
            if (not s.occupied) and (s.unique_id not in reserved)
        )

    def maybe_arrive(self):
        # cap simultaneous drivers
        if self.get_num_drivers() >= self.max_cars:
            return

        # only spawn if there is an unoccupied, unreserved space
        if self.free_unreserved_capacity() <= 0:
            return

        # do not spawn if entry cell already has a car
        if self.cell_has_driver(self.entry_pos):
            return

        if self.random.random() >= self.arrival_prob:
            return

        drv = Driver(self.next_id(), self)
        self.scheduler.add(drv)

    def step(self):
        self.maybe_arrive()
        self.scheduler.step()
        self.datacollector.collect(self)
