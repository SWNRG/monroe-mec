#!/usr/bin/python3

import os

#Italy
fname = "./2010-01-01 16:35_2017-11-28 16:35_italy_intrvl_3600.0"
#Sweden
fname = "2010-01-01 16:35_2017-11-28 16:35_sweden_intrvl_3600.0"
#Norway 
fname = "2016-01-01 16:35_2017-11-11 16:35_norway_intrvl_3600.0"
#Spain
fname = "2016-01-01 16:35_2017-11-11 16:35_spain_intrvl_3600.0"


nodes = []

# find all possible nodes in the incoming file
def scanLine(fname):
	with open(fname) as f:
		 for line in f:
		 	sub1=line.split("node: ",1)[1]
		 	sub2=sub1[0:3]
		 	if sub2 not in nodes:
		 		nodes.append(sub2)
	
	print (nodes)
		 #if "node:352" not in content:
		 	#print (content)
   
if __name__ == '__main__':
	scanLine(fname)
