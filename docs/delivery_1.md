# Modelation and Simulation - Delivery 1

### Group Description

**Group:** EIC2_12

**Group Members:**
- Marcos Costa
- Rodrigo Moucho
- Rodrigo Póvoa

### Topic 

Urban parking management, or any other high demand parking area, is a problem that affects nearly every country in the world, especially very large and busy cities. Lack of parking spaces, innefficient parking management systems alongside growing demand are some of the main causes for this problem. By modeling the drivers as agents of the system, and the parking spaces as the resources to be managed, our simulation will allow the group to test different strategies and solutions to optimize a parking system. 

This project falls under the Modelation and Simulation of Transportation Systems field of action, particularly the management and optimization of parking.

It will focus on parking lot allocation strategies and evaluating the possible different approaches, such as first-come-first-serve, pre-booking, auctions, dynamic pricing, etc. At the same time efficiency indicators for the parking system, like occupancy, waiting times, revenue and fairness will be monitored.

This issue has a significant amount of scientific literature such as "Parking Policy and Urban Mobility Level of Service – System Dynamics as a Modelling Tool for Decision Making" by João P. R. Bernardino and Maurits van der Hoofd. Additionally the European Commission's, recently founded, Park4SUMP project focuses exactly on innovative urban parking management, highlighting the relevancy this topic still possesses.

### Problem Formulation

From the point of view of Modelation and Simulation, the problem is how to efficiently distribute parking spaces to drivers.

The simulation problem can be defined in the following way:

- **Objective:** To modelate and analyze the dynamics of the interaction between drivers and parking spaces in a parking lot, under different allocation strategies. The goal is to assess how these strategies impact the chosen key performance indicators (KPIs).

- **What is to be simulated:** 
  - The arrival time of different type of vehicles and *stochastic* parking durations.
  -  The search and allocation process within the parking lot, which includes the internal circulation and gate queues.
  - The impact of different strategies.

- **Purpose:**
    - Represent drivers as agents in an environment with a limited number of parking spaces, creating simulated parking lot dynamics.
    - To compare different allocation and princing strategies **quantitatively** based on KPIs, identifying the best strategies to improve overall efficiency.


### Objectives

The main objectives of this project is:

- Analyze the system's dynamics and assess how parking systems behave under different distributions of demand and management strategies and which are the best ones.

The developed model will be:

- Descriptive because the it is used to represent and understand how a system currently works
- Prescriptive because the group will compare strategies to find the best outcomes


### System Model

#### 1. Components and Entities

1. **Users / Drivers**  
   - Classes: `GENERAL`, `EV`, `PMR` (probabilities π_GEN, π_EV, π_PMR).  
   - States: ARRIVING_QUEUE | ENTERING_GATE | SEARCHING | PARKED | HEADING_TO_EXIT | EXIT_QUEUE | EXITED.

2. **Parking Spaces**  
   - Zones/Types: General, EV (Electric Vehicles), PMR (Reduced Mobility).  

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

5. **Management**
    - Current price: `P(t)`
    - Cumulative revenue at time t: `R(t)`
    - Allocation strategy in use: `Strategy(t)`
    - *More variables to be defined based on strategies.*

#### 3. Key Performance Indicators (KPIs)

Key Performance Indicators include (may be altered):

- **Occupancy of Parking Lot**
- **Turn-away Rate**
- **Time in System**
- **Access time decomposition** (gate wait + internal circulation + exit wait)

In strategies with money allocations:

- **Revenue Rate**

### 4. Decision criterion /Operation policies / Scenarios

The decision criterion is the optimization of parking system performance based on key KPIs.

Operation policies and scenarios to be simulated include:

- Baseline: First-Come-First-Serve (FCFS).

- Reservation-Based: Pre-booking with guaranteed spots.

- Market-Driven: Auction or bidding for available spaces.

- Dynamic Pricing: Real-time price adjustment based on occupancy.

### 4. Decision support model

**Inputs - Uncontrollable / Exogenous**:

- Arrival rate of vehicles λ(t) (demand intensity).

- Vehicle type distribution (π_GEN, π_EV, π_PMR).

- Parking duration distribution D.

**Inputs - Controllable / Exogenous**:

- Allocation strategy (FCFS, Pre-Booking, Auction, Dynamic Pricing).

- Pricing policy parameters (base rate, adjustment rules).

- Capacity configuration (C_GEN, C_EV, C_PMR).

- Number of gates (G_in, G_out).

**Output**:

- Occupancy rate.

- Turn-away rate.

- Average waiting and search times.

- Average time in system.

- Revenue rate.

### Data requirements

Synthetic data will be generated through simulation, representing arrival rate of vehicles, vehicle type distribution, parking duration and other required data.

All data will be self-generated allowing for quick changes in order to test different hypothesis and distributions. Parameter values will be defined based on realistic assumptions.

- Drivers behave rationally according to the current operational policies.

- EV, PMR and reserved spots will be respected by drivers.

The systems space encompasses a closed parking lot which can only be accessed through gates (entry/exit) and has an internal circulation network. The system can be defined by the interactions between the driving agents with the parking infrastructure under particular operational policies.


### Methods & Tools

The project is to developed using the **Python** language, as it provides a large range of libraries and tools for data analysis and simulation.

Regarding the simulation environment, either the well known libraries **Simpy** or **Mesa** are going to be used (although we are more inclined towards **Mesa**), as they allow us to asynchronously model discrete-event simulations and agent-based simulations, such as vehicles arrivals, gate queues, etc.

The simulation will be built on Event-Oriented and Agent-based discrete models, to easily manage multiple entities.

The KPIs, or Key Performance Indicators, generated by the simulation will be analyzed using data analysis libraries such as **Pandas** and **NumPy**, which then later can be visualized in plots using **Matplotlib** or **Seaborn** popular libraries, to better understand the system's behavior.



### Large Language Models

An LLM was used as a refinement tool to help clarify ideas and support decision-making.

For instance, it assisted in the debate of how to represent the PMR and EV reserved spots and what benefits/drawbacks this decision entailed.

It also helped to confirm and validate possible doubts the group had regarding standard practices in simulation-based transportation system studies.

Overall, the use of the LLM was positive by supporting and accelerating the project proposal process. Most importantly, an attentive and careful review of its suggestions was always employed, ensuring all content was correct and aligned with the group's vision.
