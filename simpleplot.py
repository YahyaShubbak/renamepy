# -*- coding: utf-8 -*-
"""
Created on Sat Oct 23 13:58:03 2021

@author: yshub
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.colors as mcolors
import os
import scipy.constants as con

datapath = 'C:/Users/yshub/Dropbox/01_Uni Valenica/01_Spin Crossover research/'
excel_file = pd.read_excel(datapath+'Databook.xlsx',sheet_name='SCO6_50nm')

t = excel_file['t / minutes']
T = excel_file['T / K']
P = excel_file['P / mbar']
R = excel_file['Rate / A / s']

fig=plt.figure()
ax=fig.add_subplot(111, label="1")
ax2=fig.add_subplot(111, label="2", frame_on=False)
ax3=fig.add_subplot(111, label="2", frame_on=False)


ax.plot(t, T,color="C0")
ax.set_xlabel("Time / minutes")
ax.set_ylabel("Temperature / K", color="C0")


ax2.plot(t, P, color='C1')
# ax2.set_xlabel("Pressure / mbar")
ax2.yaxis.tick_right()
ax2.set_ylabel("Pressure / mbar", color="C1")
ax2.yaxis.set_label_position('right') 

sc = ax3.scatter(t,R, c=R, marker='x')
ax3.set_xticks([])
ax3.set_yticks([])
cbar = fig.colorbar(sc, orientation='vertical', label= 'rate / A / s')

plt.show()

#%%
t = excel_file['t / minutes']
T = excel_file['T / K']
P = excel_file['P / mbar']
R = excel_file['Rate / A / s']

fig2=plt.figure()
ax=fig2.add_subplot(111, label="1")
ax2=fig2.add_subplot(111, label="2", frame_on=False)
# ax3=fig2.add_subplot(111, label="2", frame_on=False)




ax.plot(T, R,color="C0")
ax.set_xlabel("T / K")
ax.set_ylabel("Rate / A / s", color="C0")
ax.tick_params( bottom=False, left=False, right=False,top=False,direction='in')

ax2.plot(T, P, color='C1')
# ax2.set_xlabel("Pressure / mbar")
ax2.yaxis.tick_right()
ax2.set_ylabel("Pressure / mbar", color="C1")
ax2.yaxis.set_label_position('right') 
ax2.tick_params(left=True, right=True,top=True,direction='in')

# sc = ax3.scatter(t,R, c=R, marker='x')
# ax3.set_xticks([])
# ax3.set_yticks([])
# cbar = fig.colorbar(sc, orientation='vertical', label= 'rate / A / s')

plt.show()

fig3, ax3 = plt.subplots(3,1, sharex=True)

ax3[0].scatter(t, T, marker='.')
# ax3[0].set_xlabel("T / K")
ax3[0].set_ylabel("Temperature / K")
ax3[0].tick_params( bottom=True, left=True, right=True,top=True,direction='in')
ax3[0].vlines(x=18, ymin=min(T), ymax=max(T), color='gray', linestyle='dotted')


ax3[2].scatter(t, P*10**7, marker='.')
ax3[2].set_ylabel("Pressure / $10^{-7}\,$mbar")
ax3[2].tick_params(bottom=True, left=True, right=True,top=True,direction='in')
ax3[2].set_xlabel("time / 60 s")
ax3[2].vlines(x=18, ymin=min(P*10**7), ymax=max(P*10**7), color='gray', linestyle='dotted')

ax3[1].scatter(t, R, marker='.')
ax3[1].set_ylabel("Rate / $\AA$ / s")
ax3[1].tick_params( bottom=True, left=True, right=True,top=True,direction='in')
ax3[1].vlines(x=18, ymin=min(R), ymax=max(R), color='gray', linestyle='dotted')

plt.savefig(datapath+'p_T_R_plot.png', bbox_inches='tight', dpi=300, transparent=False)




