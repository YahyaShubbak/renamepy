# -*- coding: utf-8 -*-
"""
Created on Mon Jul 19 11:41:10 2021

@author: yshub
"""

import numpy as np # For data manipulation
import matplotlib.pyplot as plt # For doing the plots
from copy import deepcopy
import math

M1M2={
"Sample1" : 0.185915063,
"Sample2" : 0.464787658,
"Sample3" : 0.929575316,
"Sample4" : 1.859150632,
"Sample5" : 4.647876579,
}

M2M1={
"Sample1" : 5.378800313,
"Sample2" : 2.151520125,
"Sample3" : 1.075760063,
"Sample4" : 0.537880031,
"Sample5" : 0.215152013,

      }

m1m2 ={
"Sample1" : 0.424929178,
"Sample2":1.079136691,
"Sample3":1.960784314,
"Sample4":4.054054054,
"Sample5":9.375,
}

m2m1 = { 
"Sample1" : 2.353333333,
"Sample2" : 0.926666667,
"Sample3" : 0.51,
"Sample4" : 0.246666667,
"Sample5" : 0.106666667,

        }
M1={
"Sample1" : 0.017455593,
"Sample2" : 0.034911186,
"Sample3" : 0.043638982,
"Sample4" : 0.052366779,
"Sample5" : 0.043638982,
}

M2={
"Sample1" : 0.093890149,
"Sample2" : 0.075112119,
"Sample3" : 0.046945074,
"Sample4" : 0.028167045,
"Sample5" : 0.009389015,
}

m1= {
"Sample1" : 0.298210736,
"Sample2" : 0.519031142,
"Sample3" : 0.662251656,
"Sample4" : 0.802139037,
"Sample5" : 0.903614458,
     }

m2= {
"Sample1" :0.701789264,
"Sample2" :0.480968858,
"Sample3" :0.337748344,
"Sample4" :0.197860963,
"Sample5" :0.096385542,
     }

def getintersection(b1, b2, m1, m2):
    xi = (b1-b2) / (m2-m1)
    yi = m1 * xi + b1
    return (xi, yi)

fig, ax = plt.subplots()
x = np.linspace(-10, 10, 2)
functions = []
m = []
b = []
for i in range(1,6):
    mi = m1m2["Sample"+str(i)]*(M2M1["Sample"+str(i)])**2
    bi = (M2M1["Sample"+str(i)]*(m1m2["Sample"+str(i)]-1))
    fx = mi*x + bi
    
    m.append(mi)
    b.append(bi)
    
    plt.xlim(0, 1.3)
    plt.ylim(1.6, 2.5)

    plt.plot(x, fx)
    print(fx)
    functions.append(fx)

intersections_x = [ ]
intersections_y = [ ]
unique_intersections = { }

for index, mi in enumerate(m):
    others_m = deepcopy(m)
    others_m.pop(index)
    others_b = deepcopy(b)
    others_b.pop(index)
    for i, o in enumerate(others_m):
        tx, ty = getintersection(b[index], others_b[i], m[index], others_m[i])
        intersections_x.append(tx)
        intersections_y.append(ty)
        unique_intersections["x"+str(round(tx,6))+"y"+str(round(ty, 6))]={"x":tx, "y":ty}
      
unique_intersections_x_y = list(unique_intersections.values())

plt.scatter(intersections_x, intersections_y, marker='x')
ax.set_xlabel("r$_2$")
ax.set_ylabel("r$_1$")

center=(max(intersections_x)+min(intersections_x))/2., (max(intersections_y)+min(intersections_y))/2
plt.scatter(center[0],center[1], color='r')
radius = ((max(intersections_y) - center[1])**2 + (intersections_x[0]-center[0])**2 )**0.5
circle1 = plt.Circle((center[0], center[1]),radius, color='k', linestyle='dotted',  fill=False)
ax.add_patch(circle1)
print("r2:", center[0], "r1: ", center[1])

legend=["Sample 1", "Sample 2", "Sample 3", "Sample 4", "Sample 5", "Enclosure", "Intersection", "Center point"]
ax.legend(legend)

fig.savefig('mayo', bbox_inches='tight', dpi=300, transparent=False)

distances = []
errors = []
for index, x in enumerate(unique_intersections):
    dist = math.hypot(center[0] - unique_intersections_x_y[index]["x"], center[1] - unique_intersections_x_y[index]["y"] )
    error = abs(dist)- radius
    error = abs(error)
    distances.append(dist)
    errors.append(error)

mean_error = np.mean(errors)

#%%###############        Ross and Lewis
ross_array_x = [ ]
ross_array_y =[ ]
fig2, ax2 = plt.subplots()

xerrlist = [0.022152007,
0.046776389,
0.116158368,
0.306536397,
1.476875822,
]
yerrlist = [-0.06852039,
0.007964344,
0.120058199,
0.503551842,
2.661179745,
]

for i in range(1,6):
    x = (M1M2["Sample"+str(i)])**2*m2m1["Sample"+str(i)]
    y = M1M2["Sample"+str(i)]*(1-m2m1["Sample"+str(i)])
    ross_array_x.append(x)
    ross_array_y.append(y)
    
    # xerr = abs(0.1*x)
    # xerrlist.append(xerr)
    # yerr = abs(0.5*y)
    # yerrlist.append(yerr)

ross_array_x = np.asarray(ross_array_x)
ross_array_y = np.asarray(ross_array_y)
#obtain m (slope) and b(intercept) of linear regression line
m, b = np.polyfit(ross_array_x, ross_array_y, 1)
print('m:', m, 'b:', b)

for i, (xerr, yerr) in enumerate(zip(xerrlist, yerrlist)):
    ax2.errorbar(ross_array_x[i],ross_array_y[i], xerr=xerrlist[i], yerr=yerrlist[i], ecolor='gray', elinewidth=1, capthick=2)
    print("xerr:", xerr)
    print("yerr", yerr)


#add linear regression line to scatterplot 
x2 = np.linspace(0,4,2)
plt.xlim(0,4)
plt.plot(x2, m*x2+b, linestyle='dotted', color='k')
plt.scatter(ross_array_x,ross_array_y, color='red', marker='x')


legend2 = ["Linear regression: $y=1,976x - 0.375$", "Samples"]
ax2.legend(legend2)
ax2.set_xlabel("[M$_1]^2$/[M$_2]^2\cdot $m$_2/$m$_1$")
ax2.set_ylabel("[M$_1]$/[M$_2]\cdot ($1-m$_2/$m$_1$)")
fig2.savefig('Ross', bbox_inches='tight', dpi=300, transparent=False)

#%%############# copolymersiation diagram
#######    https://blog.finxter.com/np-polyfit/
fig3, ax3 = plt.subplots()
x2 = np.linspace(0,1, 2 )
y2 = np.linspace(0,1, 2 )
x_codiagram = [0]
y_codiagram = [0]

xerrlist_2 = [0,0.002688974,
0.006068397,
0.013949821,
0.031918468,
0.132354751, 0
]
yerrlist_2 = [0, 0.056335922,
0.078005277,
0.114926633,
0.212595751,
0.473569277, 0
]


for i in range(1,6):
    x = (M1["Sample"+str(i)]/(M1["Sample"+str(i)]+M2["Sample"+str(i)]) )
    y = (m1["Sample"+str(i)]/(m1["Sample"+str(i)]+m2["Sample"+str(i)]) )
    x_codiagram.append(x)
    y_codiagram.append(y)
    
    # xerr = abs(0.1*x)
    # xerrlist_2.append(xerr)
    # yerr = abs(0.1*y)
    # yerrlist_2.append(yerr)
    
x_codiagram.append(1)
y_codiagram.append(1)

for i, (xerr, yerr) in enumerate(zip(xerrlist_2, yerrlist_2)):
    ax3.errorbar(x_codiagram[i],y_codiagram[i], xerr=xerrlist_2[i], yerr=yerrlist_2[i], ecolor='gray', elinewidth=1, capthick=2)
    print("xerr_2:", xerr)
    print("yerr_2", yerr)
    
ax3.scatter(x_codiagram,y_codiagram, color="r", marker="x")
ax3.plot(x2, y2, color="orange")  
# ax3.plot(x_codiagram,y_codiagram, linestyle="solid")
fit = np.polyfit(np.asarray(x_codiagram), np.asarray(y_codiagram), 2)
a = fit[0]
b = fit[1]
c = fit[2]
fit_equation = a * np.square(np.asarray(x_codiagram)) + b * np.asarray(x_codiagram) + c

plt.plot(np.asarray(x_codiagram), fit_equation, linestyle='dotted', color='k')

ax3.set_xlabel("M$_1$/(M$_1$+M$_2$)")
ax3.set_ylabel("m$_1$/(m$_1$+m$_2$)")
ax3.set_xlim(0,1)
ax3.set_ylim(0,1)

legend3 = ["ideal azeotrope, $r_1$ = $r_2$ = 1", "guidance for the eye", "M1, $r_1$ = 2.08"]
ax3.legend(legend3)
fig3.savefig('Copolydiagram', bbox_inches='tight', dpi=300, transparent=False)


#%%##### Q, e
fig4, ax4 = plt.subplots()

# qe = {
# "MMA_exp" : [0.73281289 ,	-1.296463646],
# "Styrol":	[1,	-0.8],
# "MMA_lit"	:[0.74,	0.4],
# "acrolein":	[0.85,	0.73],
# "vibylchlorid":	[0.044,	-0.2] }

qe = {
"2":	[1,	-0.8],
"3"	:[0.74,	0.4],
"4":	[0.85,	0.73],
"5":	[0.044,	-0.2] }

plt.scatter(0.73281289 , -1.296463646, marker = "x")

for i in range(2,6):
    plt.scatter(qe[str(i)][0], qe[str(i)][1])

ax4.set_xlabel("Q")
ax4.set_ylabel("e")
ax4.set_xlim(0,1.1)
ax4.set_ylim(-2,2)

legend4 = ["Quadrant separation linie", "MMA_exp", "Styrol",  "MMA_lit", "acrolein", "vibylchlorid"]
ax4.axvline(x=0.35, linestyle = "dotted")
ax4.legend(legend4)

ax4.axhline(y=0, color= "k", linewidth=1)
fig4.savefig('qe-diagram', bbox_inches='tight', dpi=300, transparent=False)