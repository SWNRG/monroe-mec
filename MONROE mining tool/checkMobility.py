#!/usr/bin/python3

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from calendar import timegm
from time import struct_time, strftime, gmtime
from dateutil.relativedelta import relativedelta
from datetime import datetime
import argparse
import sys
from pyproj import Proj
import requests

###############################################################################
def ParseCommandLine():
    parser = argparse.ArgumentParser(description = "Modem status - GPS to KML mapper")
    # parser.add_argument('-n', '--nodeID', help = 'ID of the node to analyze', required = True, type = int)
    parser.add_argument('-p', '--project', help = 'Project to retrieve data for', required = True)
    parser.add_argument('-s', '--startTime', help = 'Starting timestamp', required = True)
    parser.add_argument('-e', '--endTime', help = 'Ending timestamp', required = True)
    parser.add_argument('-c', '--certificate', help = 'Path to the client certificate used for server authentication', required = True)
    parser.add_argument('-k', '--privateKey', help = 'Path to the private key used for server authentication', required = True)
    
    args = parser.parse_args()

    # Validate args
    if (args.endTime < args.startTime):
        print("End time must be greater than start time")
        sys.exit()

    args.startDateTime = datetime.strptime(args.startTime, "%Y-%m-%d %H:%M")
    args.endDateTime = datetime.strptime(args.endTime, "%Y-%m-%d %H:%M")
    
    epoch = datetime.utcfromtimestamp(0)
    
    args.startTimeStamp = int((args.startDateTime - epoch).total_seconds());
    args.endTimeStamp = int((args.endDateTime - epoch).total_seconds());

    # Print parameters
    # print("The following command line arguments can be used:")
    # print("NodeID: {}".format(args.nodeID))
    print("Project: {}".format(args.project))
    print("StartTime: {} ({})".format(args.startTime, args.startTimeStamp))
    print("EndTime: {} ({})".format(args.endTime, args.endTimeStamp))
    return args

###############################################################################

if __name__ == '__main__':
    args = ParseCommandLine()

    response = requests.get('https://scheduler.monroe-system.eu/v1/resources', cert=(args.certificate, args.privateKey))

    if response.status_code != 200:
        # This means something went wrong.
        print('GET /v1/resources {}'.format(response.status_code))
        print('Response Headers: {}'.format(response.headers))
        sys.exit()
        
    authProvider = PlainTextAuthProvider(username='monroedb', password='monroedb_pass')
    cluster = Cluster(['127.0.0.1'], 9042, auth_provider = authProvider, connect_timeout = 15)
    session = cluster.connect('monroe')
    
    runningStart = args.startDateTime
    
    while True:
        runningEnd = datetime(runningStart.year, runningStart.month, runningStart.day + 1)
        if runningEnd > args.endDateTime:
            runningEnd = args.endDateTime
        
        epoch = datetime.utcfromtimestamp(0)
        
        runningStartTimeStamp = int((runningStart - epoch).total_seconds());
        runningEndTimeStamp = int((runningEnd - epoch).total_seconds());
        
        noGpsDataCount = 0
        noMobilityCount = 0
        mobilityCount = 0
        
        for resource in response.json():
            # print('{} {}'.format(resource['id'], resource['project']))
            
            if resource['project'] == args.project and (resource['type'] == 'deployed' or resource['type'] == 'testing'):
                # GPS data
                #print("SELECT nodeid, timestamp, latitude, longitude FROM monroe_meta_device_gps WHERE nodeid = '" + str(resource['id']) + "' AND timestamp >= " + str(args.startTimeStamp) + " AND timestamp <= " + str(args.endTimeStamp) + " ALLOW FILTERING")
                gpsRows = session.execute("SELECT nodeid, timestamp, latitude, longitude FROM monroe_meta_device_gps WHERE nodeid = '" + str(resource['id']) + "' AND timestamp >= " + str(runningStartTimeStamp) + " AND timestamp <= " + str(runningEndTimeStamp) + " ALLOW FILTERING", timeout = 20000)
                if not gpsRows:
                    noGpsDataCount += 1
                else:
                    latitude = gpsRows[0].latitude
                    longitude = gpsRows[0].longitude
                    found = False
                    
                    for row in gpsRows:
                        if row.latitude != latitude or row.longitude != longitude:
                            # print ( "node: {}, row.latitude: {:f}, latitude: {:f}, row.longitude: {:f}, longitude: {:f} ".format(row.nodeid, row.latitude, latitude, row.longitude, longitude ) )
                            mobilityCount += 1
                            found = True
                            break

                    if not found:
                        noMobilityCount += 1
        
        print("Interval: {} - {}, Total Nodes: {}, No GPS data nodes: {}, Mobile nodes: {} ".format(str(runningStart), str(runningEnd),  str(noGpsDataCount + noMobilityCount + mobilityCount), str(noGpsDataCount), str(mobilityCount) ))

        runningStart = runningEnd
        
        if runningEnd == args.endDateTime:
            break
   
    cluster.shutdown

