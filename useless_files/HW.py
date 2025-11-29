#1c)
import numpy as np
from scipy.integrate import quad

y0 = 10.0
vx0 = 1.0
vy0 = 1.0
xf = 1.0
g = 9.81
E = 0.5*(vx0**2 + vy0**2) + g*y0
print(E)

def y_true(x):
    return y0 + (vy0/vx0)*x - 0.5*g*x**2 / vx0**2

def dy_dx(x):
    return vy0/vx0 - g*x/vx0**2

def integrand(x):
    return np.sqrt(2*(E - g*y_true(x))) * np.sqrt(1 + dy_dx(x)**2)

S_true, _ = quad(integrand, 0, xf)
print("Action = ", S_true)

#1d)
def f(x):
    return x*(x - xf)

def dy_trial_dx(x, lam):
    return dy_dx(x) + lam*(2*x - xf)

def y_trial(x, lam):
    return y_true(x) + lam*f(x)

def integrand_trial(x, lam):
    return np.sqrt(2*(E - g*y_trial(x, lam))) * np.sqrt(1 + dy_trial_dx(x, lam)**2)

lambdas = [-0.2, -0.1, 0.1, 0.2]
for lam in lambdas:
    S_trial, _ = quad(lambda x: integrand_trial(x, lam), 0, xf)
    print(f"Lambda = {lam}, Action = {S_trial}, Difference = {S_trial - S_true}")