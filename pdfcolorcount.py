# -*- coding: utf-8 -*-
"""
Created on Fri Dec 31 01:38:43 2021

@author: yshub
"""

import pdf2image as pdf
import numpy as np

pdffile = pdf.convert_from_path('C:/Users/yshub/Desktop/Master_Thesis_Spin_Crossover (13).pdf')
bw=0
color=0
for image in pdffile:
    img = np.array(image.convert('HSV'))
    hsv_sum = img.sum(0).sum(0)
    if hsv_sum[0] == 0 and hsv_sum[1] == 0:
        bw += 1
    else:
        color += 1
print('bw: ',bw, 'color: ',color, 'total: ', bw+color )

print('cost: ', bw*0.1+color*0.3)