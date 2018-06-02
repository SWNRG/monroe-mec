#!/usr/bin/python3
import os

fileIn='./inFile'
fileOut='./monroe-positions'

nodePrev = 0
nodeCur = 0
nodeIterator = 1
timeIterator = 0.0
x_max = 0.0
y_max = 0.0
x_min = 800000
y_min = 9000000
temp=[]

new_dimen_x = 150
new_dimen_y = 150


# first need to find tha relative x_min, y_min in the whole file
with open(fileIn) as fp:
   # these lines execute ONCE
   line = fp.readline()
   cnt = 0
   # iterate through all the file lines
   while line:
      cnt+=1
      
      coordX = line.partition(', x: ')[2]
      coordX =  coordX.partition(', y: ')[0]
      coordY =  line.partition(', y: ')[2]

      coordX = float(coordX)
      coordY = float(coordY)

      if(coordX<x_min):
         x_min = coordX
         #print("x_min:", x_min)
      if(coordY<y_min):
         y_min = coordY
         #print("y_min:", y_min)

      if(coordX>x_max):
         x_max = coordX
         #print("x_max:", x_min)
      if(coordY>y_max):
         y_max = coordY
         #print("y_max:", y_min)

      # read next line
      line = fp.readline()
      
   print("Lines read: ",cnt," Final Results:")
   print("x_min:", x_min)
   print("y_min:", y_min)
   print("x_max:", x_max)
   print("y_max:", y_max)
   print("finished min/max")
   
   
def transform_x(coordX):
   return ((coordX - x_min + 0.000001)/x_diff)*new_dimen_x

def transform_y(coordY):
   return ((coordY - y_min + 0.000001) / y_diff) * new_dimen_y


x_diff = x_max - x_min
y_diff = y_max - y_min

fp = open(fileIn,'r')
rp = open(fileOut, 'w')

#these lines execute ONCE
line = fp.readline()
cnt=1
similarityCounter = 0
try:
   #iterate through all the file lines
   while line:
      cnt += 1 #total lines counter
      #print("round:", cnt)

      #line to compare with the next
      linePrev = line

      nodePrev = line.partition('node: ')[2]
      nodePrev = nodePrev.partition(', time:')[0]

      coordX_Prev = linePrev.partition(', x: ')[2]
      coordX_Prev = coordX_Prev.partition(', y: ')[0]
      coordY_Prev = linePrev.partition(', y: ')[2]

      coordX_Prev = float(coordX_Prev)
      coordY_Prev = float(coordY_Prev)


      #next line to compare
      line = fp.readline()
      nodeCur = line.partition('node: ')[2]
      nodeCur = nodeCur.partition(', time:')[0]


      coordX = line.partition(', x: ')[2]
      coordX = coordX.partition(', y: ')[0]
      coordY = line.partition(', y: ')[2]

      coordX = float(coordX)
      coordY = float(coordY)

      if(coordX_Prev == coordX and coordY_Prev == coordY):
         similarityCounter+=1
         #print(similarityCounter)
      else:
         similarityCounter=0
         # only the useful will be transformed for cooja dimensions (default: 150X150)
         coordX = transform_x(coordX)
         coordY = transform_y(coordY)
         line2write = str(nodeIterator)+' '+str(timeIterator)+' '+str(coordX)+' '+str(coordY)+"\n"
         timeIterator = round(timeIterator+0.2,1) # first write, then increase
         temp.append(line2write)

      #every time a new node appears, increase the node number, and reset the timer
      if (nodeCur != nodePrev):#node number needs to be increased
         print('station counter: ',nodeIterator,'Final time counter: ', timeIterator)

         #print('next node appears, no increase yet')
         #only write into file stations with alot of DISTINCT movements
         if(timeIterator>700):
            # only increase the node number if succesfuly inserted a node inot file
            nodeIterator += 1
            print('node increased: ',nodeIterator)
            #print('first line to write after iter>700: ',temp[0])
            
            # write line to outFile
            for item in temp:
               rp.write(item)
            # erase the temp list, After succesfuly writing to output file
            temp = []

         else: #erase the temp list, but DONT WRITE this node, since data are not enough
            temp = []

         #reset time for every next node, DISREGARDING the length of data provided by the previous
         timeIterator = 0.0

except Exception as e:
   print("Error: ", e, ' line number: ', cnt)

# it never reaches here ??????
print('total lines:', str(cnt))

#write to output file the total number of nodes
#rp.seek(0,0)
#rp.write("\n")

#rp.write('#total nodes: '+str(nodeIterator)+"\n")

rp.close()
fp.close()



