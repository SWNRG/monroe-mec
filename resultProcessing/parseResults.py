#!/usr/bin/python

import json
import sys
import time
import io
import datetime
import argparse

###############################################################################
def ParseCommandLine():
    parser = argparse.ArgumentParser(description = "Monroe UomPing experiment result processing.")
    parser.add_argument('-i', '--input', help = 'Input file', required = True)
    parser.add_argument('-o', '--output', help = 'Output file', required = True)
    
    
    args = parser.parse_args()
    return args
    
###############################################################################

if __name__ == '__main__':
    args = ParseCommandLine()
    
#    args.input

    speedSumDynamic = 0
    lineNumDynamic = 0
    speedSumStatic = 0
    lineNumStatic = 0
    
    # Output log list entries to file
    with io.open(args.input, 'r') as inputFile, io.open(args.output, 'w') as outputFile:
        outputFile.write(unicode("Timestamp, Url, Operator, Speed\n"))

        for line in inputFile:
            jsonLine = json.loads(line)
            if jsonLine["DataId"] == "MONROE.EXP.UOMPING.CURL":
                if jsonLine["DynamicSelection"]:
                    outputFile.write( unicode(str(jsonLine["Timestamp"]) + ", " + jsonLine["Url"] + ", " + str(jsonLine["Speed"]) + ", " + jsonLine["Operator"] + ", " + str(jsonLine["DynamicSelection"]) + "\n" ) )                
                    speedSumDynamic += jsonLine["Speed"]
                    lineNumDynamic += 1

        inputFile.seek(0)

        for line in inputFile:
            jsonLine = json.loads(line)
            if jsonLine["DataId"] == "MONROE.EXP.UOMPING.CURL":
                if not jsonLine["DynamicSelection"]:
                    outputFile.write( unicode(str(jsonLine["Timestamp"]) + ", " + jsonLine["Url"] + ", " + str(jsonLine["Speed"]) + ", " + jsonLine["Operator"] + ", " + str(jsonLine["DynamicSelection"]) + "\n" ) )
                    speedSumStatic += jsonLine["Speed"]
                    lineNumStatic += 1

                    
    if lineNumDynamic > 0 :
        print "Average speed dynamic = " + str(speedSumDynamic / lineNumDynamic) + " bytes/sec"
    else:
        print "No dynamic data"

    if lineNumStatic > 0 :
        print "Average speed static = " + str(speedSumStatic / lineNumStatic) + " bytes/sec"
    else:
        print "No static data"
