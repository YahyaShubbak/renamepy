#from cmath import pi
import numpy as np # For data manipulation
import matplotlib.pyplot as plt # For doing the plots
plt.style.use('dark_background')

x = np.linspace(0,2,1000)
y = 2*np.cos(np.pi*x)+1
def func():
    return 2*np.cos(np.pi*x)+1


fig, ax = plt.subplots(facecolor = '0.1175')
ax.plot(x, func())
ax.spines['bottom'].set_position(('data', 0))
ax.tick_params(left=True, right=True,top=True,direction='in',)
plt.show()