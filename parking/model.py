from mesa import Agent, Model
import random
import math

# Agents

class Driver(Agent):

    def __init__(self,unique_id, model, driver_type="GENERAL", parking_duration=None):
        super().__init__(unique_id, model)
        self.driver_type = driver_type
        if parking_duration is None:
            self.parking_duration = max(1, int(random.lognormvariate(math.log(30), 0.5)))
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
            else:
                self.state = "EXITED"

        elif self.state == "WAITING":
            self.wait_time += 1
            if self.model.waiting_queue and self.model.waiting_queue[0] == self:
                if random.random() < self.model.gate_release_prob:
                    self.state = "SEARCHING"
                    self.model.waiting_queue.pop(0)
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
                    space.occupied = False
                    space.occupant = None
                self.state = "EXITING"

        elif self.state == "EXITING":
            if random.random() < 0.4:
                self.state = "EXITED"

        
    
class ParkingSpace(Agent):



# Model

class ParkingLotModel(Model):

