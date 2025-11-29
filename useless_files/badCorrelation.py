import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

np.random.seed(0)

# r from 0 to 1 in steps of 0.01
r_values = np.arange(0.0, 1.01, 0.01)
n_points = 200  # more points = more numerical precision

# Shared x (standardized)
x = np.linspace(-3, 3, n_points)
x = (x - np.mean(x)) / np.std(x)

# Prepare figure
fig, ax = plt.subplots(figsize=(5, 5))
scat = ax.scatter([], [], s=30, alpha=0.8)
ref_line, = ax.plot(x, x, color="red", lw=2, label="y = x")
text = ax.text(-0.5, 3.4, "", fontsize=12)

ax.set_xlim(-3, 3)
ax.set_ylim(-3, 3)
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.grid(True)
ax.legend(loc="upper left")

def make_orthonormal_z(x, rng):
    """Produce a z orthogonal to x, mean 0, std 1."""
    z_raw = rng.normal(size=x.shape)
    proj = (np.dot(x, z_raw) / np.dot(x, x)) * x
    z = z_raw - proj
    z -= np.mean(z)
    std = np.std(z)
    if std == 0:
        raise RuntimeError("Generated orthogonal component has zero std; try increasing n_points.")
    return z / std

# Pre-generate orthonormal z vectors for deterministic frames
rng = np.random.default_rng(0)
zs = [make_orthonormal_z(x, rng) for _ in r_values]

def update(frame):
    r = r_values[frame]
    z = zs[frame]
    y = r * x + np.sqrt(max(0.0, 1 - r**2)) * z
    coords = np.column_stack((x, y))
    scat.set_offsets(coords)
    text.set_text(f"r = {r:.2f}")
    return scat, text

# 10× faster: 0.05 s per frame  → interval=50 ms, fps=20
ani = animation.FuncAnimation(fig, update, frames=len(r_values), interval=50, blit=False, repeat=False)
ani.save("correlation_progression_exact_r_fast.gif", writer="pillow", fps=20)

plt.close()
print("✅ Saved correlation_progression_exact_r.gif")
