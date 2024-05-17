# import numpy as np
# import matplotlib.pyplot as plt
# from mpl_toolkits.mplot3d import Axes3D

# # Define the radius
# r = 1

# # Generate coordinates
# theta = np.linspace(0, 2.*np.pi, 100)
# phi = np.linspace(0, np.pi, 100)
# theta, phi = np.meshgrid(theta, phi)
# x = r * np.sin(phi) * np.cos(theta)
# y = r * np.sin(phi) * np.sin(theta)
# z = r * np.cos(phi)

# # Create a 3D plot
# fig = plt.figure()
# ax1 = fig.add_subplot(121, projection='3d')
# ax1.set_box_aspect([1,1,1])  # equal scaling
# ax1.plot_surface(x, y, z, rstride=5, cstride=5, color='k', edgecolors='w')

# # Create a 2D projection
# ax2 = fig.add_subplot(122)
# ax2.set_aspect('equal')
# ax2.contour(x, y, z)

# plt.show()


# # Create a 3D plot
# fig = plt.figure()
# ax1 = fig.add_subplot(121, projection='3d')
# ax1.set_box_aspect([1,1,1])  # equal scaling
# ax1.plot_surface(x, y, z, rstride=5, cstride=5, color='k', edgecolors='w')

# # Create a 2D projection with a false color map of the density
# ax2 = fig.add_subplot(122)
# ax2.set_aspect('equal')
# h = ax2.hist2d(x.flatten(), y.flatten(), bins=20, cmap='viridis')  # increase number of bins

# # Add a color bar
# cbar = plt.colorbar(h[3], ax=ax2)
# cbar.set_label('Density')

# plt.show()


# import numpy as np
# import matplotlib.pyplot as plt

# # Generate a distribution of velocities
# n_particles = 1000000
# v = np.random.normal(0, 1, (n_particles, 3))  # 3D velocities

# # Calculate the speed of each particle
# speed = np.linalg.norm(v, axis=1)

# # Transform speeds to positions using VMI principles
# # In a real VMI experiment, this would be a complex transformation involving electric/magnetic fields
# # Here we just use a simple transformation for illustration
# r = speed  # radius is proportional to speed
# theta = np.random.uniform(0, 2*np.pi, n_particles)  # random direction
# x = r * np.cos(theta)
# y = r * np.sin(theta)

# # Create a 2D projection (VMI image)
# fig, ax = plt.subplots()
# h = ax.hist2d(x, y, bins=100, cmap='viridis')

# # Add a color bar
# cbar = plt.colorbar(h[3], ax=ax)
# cbar.set_label('Counts')

# plt.show()

#%%
import numpy as np
import matplotlib.pyplot as plt

# Constants
electron_mass = 9.10938356e-31  # kg
electron_charge = 1.60217662e-19  # C
volt_to_joule = electron_charge  # conversion factor

# Specify the kinetic energies of the 4 electrons

# Specify the kinetic energies of the 4 electrons
kinetic_energies = np.array([0.3, 2, 3, 4]) * volt_to_joule  # eV to J

# Generate a distribution of particles with these kinetic energies
n_particles_per_energy = np.array([1000000, 750000, 500000, 250000])  # more particles for smaller energies
kinetic_energies = np.repeat(kinetic_energies, n_particles_per_energy)

# Rest of the code remains the same

# Calculate the speed of each particle from its kinetic energy
speeds = np.sqrt(2 * kinetic_energies / electron_mass)

# Generate random directions
theta = np.random.uniform(0, 2*np.pi, len(kinetic_energies))  # azimuthal angle


phi = np.arccos(2 * np.random.random(len(kinetic_energies)) - 1)  # polar angle

# Transform speeds to positions using VMI principles
# In a real VMI experiment, this would be a complex transformation involving electric/magnetic fields
# Here we just use a simple transformation for illustration
x = speeds * np.sin(phi) * np.cos(theta)
y = speeds * np.sin(phi) * np.sin(theta)

# Create a 2D projection (VMI image)
fig, ax = plt.subplots()
h = ax.hist2d(x, y, bins=1000, cmap='viridis')

# Add a color bar
cbar = plt.colorbar(h[3], ax=ax)
cbar.set_label('Counts')
# Create a histogram of the kinetic energies
fig, ax = plt.subplots()
counts, bins, patches = ax.hist(kinetic_energies / volt_to_joule, bins=200, color='blue', alpha=0.7)

# Set the x and y labels
ax.set_xlabel('Kinetic Energy (eV)')
ax.set_ylabel('Intensity')

plt.show()

# %%
