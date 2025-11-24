from mesa import Agent, Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid
import random
import math

# Agents

class Driver(Agent):
    def __init__(self, model, driver_type="GENERAL", parking_duration=None):
        super().__init__(model) 
        self.driver_type = driver_type
        
        if parking_duration is None:
            self.parking_duration = max(1, int(self.random.lognormvariate(math.log(30), 0.5)))
        else:
            self.parking_duration = parking_duration
            
        self.remaining_time = self.parking_duration
        self.state = "ARRIVING" 
        self.assigned_space = None
        self.wait_time = 0 

    def step(self):
        if self.state == "ARRIVING":
            if len(self.model.waiting_drivers) < self.model.max_waiting:
                self.state = "WAITING"
                self.model.waiting_drivers.append(self)
                self.model.waiting_queue.append(self)
            else:
                self.state = "EXITED"
                self.remove() 

        elif self.state == "WAITING":
            self.wait_time += 1
            if self.model.waiting_queue and self.model.waiting_queue[0] == self:
                if self.random.random() < self.model.gate_release_prob:
                    self.state = "SEARCHING"
                    self.model.waiting_queue.pop(0)
                    if self in self.model.waiting_drivers:
                        self.model.waiting_drivers.remove(self)

        elif self.state == "SEARCHING":
            candidate = self.model.find_free_space_for(self.driver_type)
            if candidate:
                candidate.occupied = True
                candidate.occupant = self
                self.assigned_space = candidate.unique_id
                self.state = "PARKED"

        elif self.state == "PARKED":
            self.remaining_time -= 1
            if self.remaining_time <= 0:
                if self.assigned_space is not None:
                    space = self.model.get_space_by_id(self.assigned_space)
                    if space:
                        space.occupied = False
                        space.occupant = None
                self.state = "EXITING"

        elif self.state == "EXITING":
            if self.random.random() < 0.4:
                self.state = "EXITED"
                self.remove()

        
    
class ParkingSpace(Agent):
    def __init__(self, model, space_type="GENERAL", custom_id=None):
        super().__init__(model)
        if custom_id:
            self.unique_id = custom_id
            
        self.space_type = space_type
        self.occupied = False
        self.occupant = None    

    def step(self):
        pass




# Model
class ParkingLotModel(Model):
    def __init__(self, num_gen=20, num_ev=4, num_pmr=2, arrival_prob=0.5, max_drivers=40, max_wait=6, seed=None):
        super().__init__(seed=seed)
        
        # Define parameters
        self.num_gen = num_gen
        self.num_ev = num_ev
        self.num_pmr = num_pmr
        self.arrival_prob = arrival_prob
        self.max_drivers = max_drivers
        self.max_waiting = max_wait
        
        # Internal Queues
        self.waiting_drivers = []
        self.waiting_queue = []
        self.gate_release_prob = 0.5 

        self.total_spaces = num_gen + num_ev + num_pmr
        self.grid = MultiGrid(self.total_spaces, 1, torus=False)

        # Statistics
        self.total_search_time = 0
        self.parked_count = 0
        self.left_no_park = 0
        self.total_parked_time = 0

        # Create Parking Spaces
        idx = 0
        for i in range(self.num_gen):
            sp = ParkingSpace(self, space_type="GEN", custom_id=f"space_GEN_{i}")
            self.grid.place_agent(sp, (idx, 0))
            idx += 1

        for i in range(self.num_ev):
            sp = ParkingSpace(self, space_type="EV", custom_id=f"space_EV_{i}")
            self.grid.place_agent(sp, (idx, 0))
            idx += 1

        for i in range(self.num_pmr):
            sp = ParkingSpace(self, space_type="PMR", custom_id=f"space_PMR_{i}")
            self.grid.place_agent(sp, (idx, 0))
            idx += 1

        # Data Collector
        self.datacollector = DataCollector(
            model_reporters={
                "OccupiedSpaces": self.get_occupied_count,
                "FreeSpaces": self.get_free_count,
                "ParkedCount": lambda m: m.parked_count,
                "LeftNoPark": lambda m: m.left_no_park,
                "AverageSearchTime": self.get_average_search_time
            }
        )


# Helpers

    def get_space_by_id(self, uid):
        for agent in self.agents:
            if agent.unique_id == uid:
                return agent
            return None

    def get_occupied_count(self):
        return len([a for a in self.agents if isinstance(a, ParkingSpace) and a.occupied])

    def get_free_count(self):
        return self.total_spaces - self.get_occupied_count()


    def  get_average_search_time(self):
        if self.parked_count == 0:
            return 0
        return self.total_search_time / max(1, self.parked_count)

    def find_free_space_for(self, driver_type):
            spaces = [a for a in self.agents if isinstance(a, ParkingSpace)]
            spaces_sorted = sorted(spaces, key=lambda s: str(s.unique_id))

            if driver_type == "PMR":
                priority = ["PMR", "GEN", "EV"]
            elif driver_type == "EV":
                priority = ["EV", "GEN", "PMR"]
            else:
                priority = ["GEN", "EV", "PMR"]

            for t in priority:
                for s in spaces_sorted:
                    if (s.space_type == t) and (not s.occupied):
                        return s
            return None

# Main step

    def step(self):
        current_drivers = len([a for a in self.agents if isinstance(a, Driver)])

        if current_drivers < self.max_drivers and self.random.random() < self.arrival_prob:
            r = self.random.random()
            if r < 0.8:
                dtype = "GENERAL"
            elif r < 0.95:
                dtype = "EV"
            else:
                dtype = "PMR"
            
            drv = Driver(self, driver_type=dtype)

        self.agents.shuffle_do("step")

        self.datacollector.collect(self)


if __name__ == "__main__":
    model = ParkingLotModel()
    for i in range(20):
        model.step()
    print(f"Step {model.steps}: Occupied {model.get_occupied_count()}")