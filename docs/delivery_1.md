# Modelation and Simulation - Delivery 1

### Group Description

**Group:** EIC2_12

**Group Members:**
- Marcos Costa
- Rodrigo Moucho
- Rodrigo Póvoa

### Topic 

The field of this project is Modelation and Simulation of Transportation Systems, addressing the management and optimization of urban parking.

Urban parking, or any other high demand parking area, is a modern problem that affects nearly every city in the world, mostly on developed countries. Lack of parking spaces, innefficient parking management and systems and absurd high demand are just some of the problems caused. By modeling the drivers as agents of the system, and the parking spaces as the resources to be managed, the simulation will allow us to test different strategies and solutions to optimize the urban parking system. 

The project will focus on the parking lot allocation strategies in urban areas. The point is to evaluate the possible different approaches, such as first-come-first-serve, pre-booking, auctions, dynamic pricing, etc, to improve the efficiency indicators of the parking system, such as occupancy, waiting times, revenue and fairness.

### Problem Formulation

From the point of view of Modelation and Simulation, the problem is how to efficiently distribute parking spaces to drivers in urban areas.

The simulation problem can be defined in the following way:

- **Objective:** To modelate and analyze the dynamics of the interaction between drivers and parking spaces in urban areas, under different allocation strategies. The goal is to assess how these strategies impact key performance indicators (KPIs), such as #TODO.

- **What is to be simulated:** 
  - The arrival time of different type of vehicles and *stochastic* parking durations.
  -  The search and allocation process within the parking lot, which includes the internal circulation and gate queues.
  - The impact of different strategies.

- **Purpose:**
    - To predict the parking system's behavior under various strategies and conditions.
    - To compare these strategies **quantitatively** based on KPIs.


### Objectives

The principal objectives of this project are defined below:

- Analyze the system dynamics: To understand how urban parking systems behave under different amounts of demand, 
- Evaluate different allocation strategies:


### System Model

#### 1. Components and Entities

1. **Users / Drivers**  
   - Classes: `GENERAL`, `EV`, `PMR` (probabilities π_GEN, π_EV, π_PMR).  
   - States: ARRIVING_QUEUE | ENTERING_GATE | SEARCHING | PARKED | HEADING_TO_EXIT | EXIT_QUEUE | EXITED.

2. **Parking Spaces**  
   - Zones/types: General, EV (Electric Vehicles), PMR (Reduced Mobility).  

3. **Infrastructure Gates**  
   - Entry: G_in gates, status UP/DOWN, service-time distribution S_in, queue Q_in(t).  
   - Exit: G_out gates, status UP/DOWN, service-time distribution S_out, queue Q_out(t).

4. **Internal Circulation**  
   - Circulating vehicles N_circ(t) that affect travel/search time inside the lot.  
   - Link travel time function T_link(t) capturing congestion effects.

5. **Management**
   - Pricing policy, quotas, allocation rules, reservation/auction modules.

6. **External Environment**  
   - Time of day, arrival intensity λ(t) (NHPP), nearby events, adoption rate of EV/PMR drivers.

#### 2. System Variables

1. **Drivers/Users**  
    - Arrival time of driver i: `Arrival_i`
    - State of driver i: `State_i` ∈ {ARRIVING_QUEUE, ENTERING_GATE, SEARCHING, PARKED, HEADING_TO_EXIT, EXIT_QUEUE, EXITED}
    - Dwell time of driver i: `Dwell_i` ~ Distribution D
    - Assigned parking space of driver i: `Space_i` ∈ {GEN, EV, PMR}
    - *More variables to be defined based on strategies.*

2. **Parking Spaces**
    - Capacity of parking space type j: `C_j` for j ∈ {GEN, EV, PMR} 
    - Occupancy at time t: `O_j(t)` for j ∈ {GEN, EV, PMR}
    - Free spaces at time t: `F_j(t) = C_j - O_j(t)`
    - *More variables to be defined based on strategies.*

3. **Infrastructure Gates**
    - Number of entry gates: `G_in`
    - Number of exit gates: `G_out`
    - Service time distribution at entry gates: `S_in`
    - Service time distribution at exit gates: `S_out`
    - Queue length at entry gates at time t: `Q_in(t)`
    - Queue length at exit gates at time t: `Q_out(t)`
    - *More variables to be defined based on strategies.*

4. **Internal Circulation**
    - Drivers searching for parking at time t: `N_searching(t)`
    - Drivers leaving but on internal circulation at time t: `N_leaving(t)`
    - Total circulating vehicles at time t: `N_circ(t) = N_searching(t) + N_leaving(t)`
    - Link travel time at time t: `T_link(t)`
    - *More variables to be defined based on strategies.*

4. **Management**
    - Current price: `P(t)`
    - Cumulative revenue at time t: `R(t)`
    - Allocation strategy in use: `Strategy(t)`
    - *More variables to be defined based on strategies.*

#### 3. Key Performance Indicators (KPIs)


