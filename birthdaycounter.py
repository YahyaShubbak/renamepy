# -*- coding: utf-8 -*-
"""
Created on Wed Aug 10 20:42:06 2022

@author: yshub
"""

import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

def get_hannas_birthday():
    year    = 97
    month   = 8
    day     = 20

    birthday = datetime(2000+year,month,day)
    return birthday

def calculate_dates(original_date, now):
    delta1 = datetime(now.year, original_date.month, original_date.day)
    delta2 = datetime(now.year+1, original_date.month, original_date.day)
    
    return ((delta1 if delta1 > now else delta2) - now).days

a = np.linspace(0, 2 * np.pi, 100)

x = 16 * ( np.sin(a) ** 3 )
y = 13 * np.cos(a) - 5* np.cos(2*a) - 2 * np.cos(3*a) - np.cos(4*a)


birthday = get_hannas_birthday()
now = datetime.now()
now = now.replace(hour=0, minute=0, second=0, microsecond=0)
c = calculate_dates(birthday, now)

if c == 365:
    print('happy birthday!!')
    plt.fill_between(x, y, color='red')
else:
    print(c,'days left for to birthday')

