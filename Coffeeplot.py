import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


euro=[17.99, 13.75, 13.79, 12.49, 13.49, 9.99]
score = [3.86, 2.97, 2.83, 1.94, 1.93, 1.37]


ax, fig = plt.subplots()
fig.scatter(euro, score)
fig.set_title('Coffee Prices and Scores')
fig.set_xlabel('Price /€')
fig.set_ylabel('Score / arb. unit')

fit = np.polyfit(euro, score, 1)
fig.plot(euro, np.polyval(fit, euro), 'r-')
rsquared = stats.linregress(euro, score).rvalue**2
fig.annotate(f'Fit: {fit[0]:.2f}x + {fit[1]:.2f}, R^2={rsquared:.2f}', (10, 3.5),)
fig.tick_params(top=True, bottom=True, right=True, direction='in', colors='k', grid_color='k', grid_alpha=0.5)
plt.savefig('Coffeeplot.png', dpi=300, bbox_inches='tight', transparent=True)

plt.show()