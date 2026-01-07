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