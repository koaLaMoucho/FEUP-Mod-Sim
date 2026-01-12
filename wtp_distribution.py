import matplotlib.pyplot as plt
import random
import math
import numpy as np

# --------------------------
# Generate WTP samples
# --------------------------
mu = math.log(0.044)  # median ~0.022 €/min
sigma = 0.34
n_samples = 10000

rng = random.Random(42)  # reproducibility
wtp_samples = [rng.lognormvariate(mu, sigma) for _ in range(n_samples)]

# --------------------------
# Histogram of WTP
# --------------------------
plt.figure(figsize=(10,5))
plt.hist(wtp_samples, bins=50, color="#0077bb", edgecolor="black", alpha=0.6, label="WTP distribution")

plt.axvline(0.011, color="red", linestyle="--", label="0.011 €")
plt.axvline(0.022, color="green", linestyle="--", label="0.022 €")
plt.axvline(0.050, color="orange", linestyle="--", label="0.050 €")
plt.title("Driver Willingness-to-Pay Distribution")
plt.xlabel("€/minute")
plt.ylabel("Number of drivers")
plt.legend()
plt.show()

# --------------------------
# Percentage willing to pay ≥ price
# --------------------------
prices = np.linspace(0.005, 0.06, 200)
percent_willing = [100 * sum(1 for w in wtp_samples if w >= p) / n_samples for p in prices]

plt.figure(figsize=(10,5))
plt.plot(prices, percent_willing, color="#0077bb", lw=2)
plt.axvline(0.011, color="red", linestyle="--", label="0.011 €")
plt.axvline(0.022, color="green", linestyle="--", label="0.022 €")
plt.axvline(0.050, color="orange", linestyle="--", label="0.050 €")
plt.title("Percentage of Drivers Willing to Pay ≥ Price")
plt.xlabel("€/minute")
plt.ylabel("Percentage willing (%)")
plt.ylim(0, 105)
plt.grid(alpha=0.3)
plt.legend()
plt.show()
