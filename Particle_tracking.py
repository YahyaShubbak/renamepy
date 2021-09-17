# -*- coding: utf-8 -*-
"""
Created on Fri Jul  9 12:38:50 2021

@author: yshub
"""
import numpy as np # For data manipulation
import matplotlib.pyplot as plt # For doing the plots
from matplotlib.patches import Rectangle
import pandas as pd
import glob
import os

datapath = 'C:/Users/yshub/Downloads/SHARED_ParticleTracking/SHARED_ParticleTracking/final/COOH/'

if not os.path.exists(datapath+"Export/"):
    os.makedirs(datapath+"Export/")
        
hd_files = sorted(glob.glob(datapath+"*.h5"), key=os.path.getmtime)
# hdtest = pd.read_hdf

df = pd.read_hdf(hd_files[0])
# xy = plt.plot(df.x, df.y)

# df.hist()

# plt.plot(df)

#%%
# ###### get the particle number
# all_particles = [df.particle.unique()]
# all_particles = list(all_particles[0])
# ######
# all_delta_x = []
# ##### get the delta x of particle i in frame i+1 -i
# for n in all_particles:
#     distanz = 0
#     for i in range(len(all_particles)-1):
#         distanz += np.abs(df.x[df['particle']==n][i+1]-df.x[df['particle']==n][i])
#     print(distanz)
###### get the particle number
all_particles = [df.particle.unique()]
all_particles = list(all_particles[0])
######
all_delta_x = []
distance_x = pd.DataFrame()

##### get the delta x of particle i in frame i+1 -i
# for n in all_particles:
#     for i in range(len(all_particles)-1):
#         distanz += np.abs(df.x[df['particle']==n][i+1]-df.x[df['particle']==n][i])
#     print(distanz)

delta_x = []
delta_y = []
for n in all_particles:
    for i in range(df.x[df['particle']==n].size-1): ######### get the indexes of particle n at distance x
        diff_x = np.abs(df.x[df['particle']==n][i+1]-df.x[df['particle']==n][i])
        delta_x.append(diff_x)
        
        diff_y = np.abs(df.y[df['particle']==n][i+1]-df.y[df['particle']==n][i])
        delta_y.append(diff_y)
len_x = np.sum(delta_x)    
len_y = np.sum(delta_y)    


distance_x.insert(1,'|distance in x|',[len_x] )
#%%

delta_x = []
delta_y = []
for i in range(df.x[df['particle']==3].size-1):
    diff_x = df.x[df['particle']==3][i+1]-df.x[df['particle']==3][i]
    delta_x.append(diff_x)
    
    diff_y = df.y[df['particle']==9][i+1]-df.y[df['particle']==9][i]
    delta_y.append(diff_y)

fig1, ax1 = plt.subplots()
fig2, ax2 = plt.subplots()

ax1.plot(delta_x)
ax2.plot(delta_y, 'red')
#%%
fig3, ax3 = plt.subplots()

ax3.plot( df.x[df['particle']==74],  df.y[df['particle']==74])

# ax4.plot( df.x[df['particle']==0],  df.y[df['particle']==0])
# ax4.plot( df.x[df['particle']==10],  df.y[df['particle']==10])
# ax4.plot( df.x[df['particle']==100],  df.y[df['particle']==100])
# ax4.plot( df.x[df['particle']==9],  df.y[df['particle']==9])

#%%
fig4, ax4 = plt.subplots()

for i in range(max(df["particle"].unique())):
    x = df.x[df['particle']==i]
    y = df.y[df['particle']==i]
    ax4.plot(x, y)
# ax4.add_patch(Rectangle((680,280), width=140, height=60, 
                        # edgecolor = 'red',fill=False, lw=1))
fig4.show()
fig4.savefig(datapath+"Export/"+'Particle_plot', bbox_inches='tight', dpi=300, transparent=False)



#%%
# import plotly
# import plotly.graph_objs as go

# from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot


# import plotly.express as px
# # fig = px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])


# # fig = px.scatter(px.data.iris(), x="sepal_length", y="sepal_width", color="species")
# # fig.write_image("figure.png", engine="kaleido")
# x_list = []
# y_list = []
# for i in range(max(df["particle"].unique())):
#     x = df.x[df['particle']==i]
#     y = df.y[df['particle']==i]
#     x_list.append(x)
#     y_list.append(y)
# plotly.offline.plot({
#     "data": [
# plotly.graph_objs.Scatter(x=np.asarray(x),
# y=np.asarray(y), mode='markers',
# )],
# "layout": plotly.graph_objs.Layout(showlegend=False
#                                    )
#     })

#%%

# plotly.offline.plot({
# "data": [
#     plotly.graph_objs.Scatter(   
#     x=df.x,
#     y=df.y, mode='markers',
#     )],
# "layout": plotly.graph_objs.Layout(showlegend=False
# )
# })

# #%%

# fig2 = px.scatter(df.x, df.y)
# fig2.show()