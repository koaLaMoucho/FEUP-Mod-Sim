from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
import math
import random
from typing import Callable, List, Tuple

#Constants

RANDOM_SEED = 42
DAY_MINUTES = 24 * 60

P_EV = 0.18
P_PMR = 0.02
P_GEN = 1.0 - P_EV - P_PMR

DWELL_LOGNORMAL_MU = math.log(90)   # ~90 minutes median
DWELL_LOGNORMAL_SIGMA = 0.5         # variability

random.seed(RANDOM_SEED)´

##Entities

class DriverClass(Enum):
    GENERAL = auto()
    EV = auto()
    PMR = auto()

class DriverState(Enum):
    ARRIVING_QUEUE = auto()
    ENTERING_GATE = auto()
    SEARCHING = auto()
    PARKED = auto()
    HEADING_TO_EXIT = auto()
    EXIT_QUEUE = auto()
    EXITED = auto()

@dataclass
class Driver:
    id: int
    cls: DriverClass
    t_arrival_min: float  
    dwell_min: float      


## arrival flux

def lambda_per_minute(t_min):
    t_hour = (t_min % DAY_MINUTES) / 60.0
    # Baseline per hour
    if 0 <= t_hour < 6:
        lam_h = 2    #overnight
    elif 6 <= t_hour < 9:
        lam_h = 25   # morning peak
    elif 9 <= t_hour < 12:
        lam_h = 15   # late morning
    elif 12 <= t_hour < 14:
        lam_h = 20   # lunch bump
    elif 14 <= t_hour < 17:
        lam_h = 12   # afternoon
    elif 17 <= t_hour < 19:
        lam_h = 28   # evening peak
    elif 19 <= t_hour < 22:
        lam_h = 10   # tapering
    else:
        lam_h = 4    # late evening

    return lam_h / 60.0  # convert to per minute

# For thinning, we need an upper bound on λ(t)
LAMBDA_MAX_PER_MIN = 28 / 60.0  # safe upper bound from the piecewise peak above