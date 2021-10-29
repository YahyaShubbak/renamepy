# -*- coding: utf-8 -*-
"""
Created on Sat Oct 23 13:58:03 2021

@author: yshub
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.colors as mcolors

excel_file = pd.read_excel('C:/Users/yshub/Dropbox/01_Uni Valenica/01_Spin Crossover research/Databook.xlsx',sheet_name='SCO6_50nm')

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