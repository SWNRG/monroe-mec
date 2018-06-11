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
    args = parser.parse_args()

    # Validate args
    if (args.endTime < args.startTime):
        print("End time must be greater than start time")
        sys.exit()

    startDateTime = datetime.strptime(args.startTime, "%Y-%m-%d %H:%M")
    endDateTime = datetime.strptime(args.endTime, "%Y-%m-%d %H:%M")
    
    epoch = datetime.utcfromtimestamp(0)
    
    args.startTimeStamp = int((startDateTime - epoch).total_seconds());
    args.endTimeStamp = int((endDateTime - epoch).total_seconds());

    # Print parameters
    # print("The following command line arguments can be used:")
    # print("NodeID: {}".format(args.nodeID))
    print("Project: {}".format(args.project))
    print("StartTime: {} ({})".format(args.startTime, args.startTimeStamp))
    print("EndTime: {} ({})".format(args.endTime, args.endTimeStamp))
    return args

###############################################################################
def FindUtmZone(longitude, latitude):
    if longitude <= -12 or longitude  > 42 or latitude <= 0 or latitude > 72:
        sys.exit("Long = {}, lat = {}. Make sure -12 <= longitude <= 42 and 0 <= latitude <= 72!".format(longitude, latitude))
        
    if longitude >= 3 and longitude <=12 and latitude >= 56 and latitude <= 64:
        return 32
 
    runLongitude = -6
    for x in range(0, 7):
        if longitude <= runLongitude:
            return x + 29
        runLongitude += 6

if __name__ == '__main__':
    args = ParseCommandLine()

    response = requests.get('https://scheduler.monroe-system.eu/v1/resources', cert=('/home/dimitris/monroe/certificate.pem', '/home/dimitris/monroe/privateKeyClear.pem'))

    if response.status_code != 200:
        # This means something went wrong.
        print('GET /v1/resources {}'.format(response.status_code))
        print('Response Headers: {}'.format(response.headers))
        sys.exit()
        
    authProvider = PlainTextAuthProvider(username='monroedb', password='monroedb_pass')
    cluster = Cluster(['127.0.0.1'], 9042, auth_provider = authProvider, connect_timeout = 15)
    session = cluster.connect('monroe')
    
    gpsData = 0
    noGpsData = 0
    for resource in response.json():
        # print('{} {}'.format(resource['id'], resource['project']))
        
        if resource['project'] == args.project and (resource['type'] == 'deployed' or resource['type'] == 'testing'):
            # GPS data
            #print("SELECT nodeid, timestamp, latitude, longitude FROM monroe_meta_device_gps WHERE nodeid = '" + str(resource['id']) + "' AND timestamp >= " + str(args.startTimeStamp) + " AND timestamp <= " + str(args.endTimeStamp) + " ALLOW FILTERING")
            gpsRows = session.execute("SELECT nodeid, timestamp, latitude, longitude FROM monroe_meta_device_gps WHERE nodeid = '" + str(resource['id']) + "' AND timestamp >= " + str(args.startTimeStamp) + " AND timestamp <= " + str(args.endTimeStamp) + " ALLOW FILTERING", timeout = 20000)
            #gpsRows = session.execute("SELECT nodeid, timestamp, latitude, longitude FROM monroe_meta_device_gps WHERE nodeid = '491' AND timestamp >= " + str(args.startTimeStamp) + " AND timestamp <= " + str(args.endTimeStamp) + " ALLOW FILTERING", timeout = 20000)
            if not gpsRows:
                noGpsData += 1
            else:
                gpsData += 1
    
    print("Experiment: {}, Total Nodes: {}, Nodes with GPS data: {}".format(str(args.project), str(noGpsData + gpsData), str(gpsData)))
    
    cluster.shutdown
