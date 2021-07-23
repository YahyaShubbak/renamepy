# -*- coding: utf-8 -*-
"""
Created on Fri Jul  9 12:38:50 2021

@author: yshub
"""
import numpy as np # For data manipulation
import matplotlib.pyplot as plt # For doing the plots
import pandas as pd

df = pd.read_hdf('C:/Users/yshub/Dropbox/Partikeltransport/COOH_DestH2O_Si800nm_1mT_0,0625s_1_CG.h5')

# xy = plt.plot(df.x, df.y)

# df.hist()

# plt.plot(df)


delta_x = []
delta_y = []
for i in range(df.x[df['particle']==9].size-1):
    diff_x = df.x[df['particle']==9][i+1]-df.x[df['particle']==9][i]
    delta_x.append(diff_x)
    
    diff_y = df.y[df['particle']==9][i+1]-df.y[df['particle']==9][i]
    delta_y.append(diff_y)

fig1, ax1 = plt.subplots()
fig2, ax2 = plt.subplots()

ax1.plot(delta_x)
ax2.plot(delta_y, 'red')

fig3, ax3 = plt.subplots()
fig4, ax4 = plt.subplots()

ax3.plot( df.x[df['particle']==74],  df.y[df['particle']==74])

# ax4.plot( df.x[df['particle']==0],  df.y[df['particle']==0])
# ax4.plot( df.x[df['particle']==10],  df.y[df['particle']==10])
# ax4.plot( df.x[df['particle']==100],  df.y[df['particle']==100])
# ax4.plot( df.x[df['particle']==9],  df.y[df['particle']==9])

for i in range(max(df["particle"].unique())):
    x = df.x[df['particle']==i]
    y = df.y[df['particle']==i]
    ax4.plot(x, y)
    
