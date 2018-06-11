#!/usr/bin/python3
import os

fileIn='./inFile'

x_max = 0.0
y_max = 0.0
x_min = 800000
y_min = 9000000

# first need to find tha relative x_min, y_min in the whole file
with open(fileIn) as fp:
   # these lines execute ONCE
   line = fp.readline()
   cnt = 0
   # iterate through all the file lines
   while line:
      cnt+=1
      print('line: ',cnt)
      
      coordX = line.partition(', x: ')[2]
      coordX =  coordX.partition(', y: ')[0]
      coordY =  line.partition(', y: ')[2]

      coordX = float(coordX)
      coordY = float(coordY)

      if(coordX<x_min):
         x_min = coordX
         print("x_min:", x_min)
      if(coordY<y_min):
         y_min = coordY
         print("y_min:", y_min)

      if(coordX>x_max):
         x_max = coordX
         print("x_max:", x_min)
      if(coordY>y_max):
         y_max = coordY
         print("y_max:", y_min)

      line = fp.readline()
      
   print("Final Results:")
   print("x_min:", x_min)
   print("y_min:", y_min)
   print("x_max:", x_max)
   print("y_max:", y_max)
   print("finished min/max")
   #finished iteration
   #fileIn.close()
