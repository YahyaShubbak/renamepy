# -*- coding: utf-8 -*-
"""
Created on Sun Jul 31 20:11:40 2022

@author: yshub
"""

from flask import Flask
from datetime import datetime
app = Flask(__name__)

counter = 1

dt = datetime.now()
#dt = datetime.now()
timestamp = datetime.timestamp(dt)
# convert to datetime
date_time = datetime.fromtimestamp(timestamp)

# convert timestamp to string in dd-mm-yyyy HH:MM:SS
str_date_time = date_time.strftime("%d-%m-%Y, %H:%M:%S")

@app.route("/")
def main():
    global counter
    counter += 1
    with open("counter.txt", "a") as f:
        f.write('scan number '+str(counter)+str(', scanned ')+str(str_date_time)+'\n')
    return str(counter)
