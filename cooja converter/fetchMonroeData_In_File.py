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
import math
import os


###############################################################################

def ParseCommandLine():
    parser = argparse.ArgumentParser(description="GPS to x-y coordinate mapper and row aggregator")
    # parser.add_argument('-n', '--nodeID', help = 'ID of the node to analyze', required = True, type = int)
    parser.add_argument('-p', '--project', help='Project to retrieve data for', required=True)
    parser.add_argument('-s', '--startTime', help='Starting timestamp', required=True)
    parser.add_argument('-e', '--endTime', help='Ending timestamp', required=True)
    parser.add_argument('-v', '--verbose', help='Display individual rows', required=False, action="store_true")
    parser.add_argument('-i', '--interval', help='Aggregation interval in seconds (default = 5)', required=False,
                        default=5.0, type=float)
    parser.add_argument('-c', '--certificate', help='Path to the client certificate used for server authentication',
                        required=True)
    parser.add_argument('-k', '--privateKey', help='Path to the private key used for server authentication',
                        required=True)
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
# Find UTM zone from long/lat as per
# https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system#/media/File:Modified_UTM_Zones.png

def FindUtmZone(longitude, latitude):
    if longitude <= -12 or longitude > 42 or latitude <= 0 or latitude > 72:
        sys.exit("Long = {}, lat = {}. Make sure -12 <= longitude <= 42 and 0 <= latitude <= 72!".format(longitude,
                                                                                                         latitude))

    if longitude >= 3 and longitude <= 12 and latitude >= 56 and latitude <= 64:
        return 32

    runLongitude = -6
    for x in range(0, 7):
        if longitude <= runLongitude:
            return x + 29
        runLongitude += 6


###############################################################################

if __name__ == '__main__':
    args = ParseCommandLine()

    # write results to a file
    writeFileName = str(args.startTime) + "_" + str(args.endTime) + "_" + str(args.project) + "_intrvl_" + str(
        args.interval)
    print("writing to file: ./" + str(writeFileName))
    writeFile = open("./" + writeFileName, "w+")

    # Make the request to the resources api
    # response = requests.get('https://scheduler.monroe-system.eu/v1/resources', cert=('/home/dimitris/monroe/certificate.pem', '/home/dimitris/monroe/privateKeyClear.pem'))

    response = requests.get('https://scheduler.monroe-system.eu/v1/resources', cert=(args.certificate, args.privateKey))

    # In case of error print the error and exit
    if response.status_code != 200:
        # This means something went wrong.
        print('GET /v1/resources {}'.format(response.status_code))
        print('Response Headers: {}'.format(response.headers))
        sys.exit()

    # Make the connection to the database
    authProvider = PlainTextAuthProvider(username='monroedb', password='monroedb_pass')
    cluster = Cluster(['127.0.0.1'], 9042, auth_provider=authProvider, connect_timeout=15)
    session = cluster.connect('monroe')

    # Start the combining algorithm at the immediately higher multiple of 5
    step = args.interval
    initialTime = step * (args.startTimeStamp / step + 1)

    # Iterate over the nodes (each resource is a node)
    for resource in response.json():
        # print('{} {}'.format(resource['id'], resource['project']))

        # Skip nodes that do not belong to the selected product and nodes that are not in the deployed or testing state
        if resource['project'] != args.project or (resource['type'] != 'deployed' and resource['type'] != 'testing'):
            continue

        # Retrieve the GPS data and check if any rows are returned
        gpsRows = session.execute(
            "SELECT nodeid, timestamp, latitude, longitude FROM monroe_meta_device_gps WHERE nodeid = '" + str(
                resource['id']) + "' AND timestamp >= " + str(args.startTimeStamp) + " AND timestamp <= " + str(
                args.endTimeStamp) + " ALLOW FILTERING", timeout=20000)
        if not gpsRows:
            print("Node: {}, Type: {}, No GPS data.".format(str(resource['id']), str(resource['type'])))
            continue

        else:
            print("Node: {}, Type: {}, GPS data exists. Interfaces {}".format(str(resource['id']), str(resource['type']), str(len(resource['interfaces'])) ))

        # Create an iterator out of the returns rows and grab the first row
        gpsIterator = iter(gpsRows)
        gpsRowsFinished = False
        try:  # Grab initial row
            gpsRow = gpsIterator.next()
        except Exception:
            gpsRowsFinished = True

        interfacesMap = {}  # Initialize a map to store each interface values

        # Iterate over all interfaces of the node
        for interface in resource['interfaces']:
            iccid = interface['iccid']

            # Initialize a map for the current interface that will hold the interface-related variables
            interfacesMap[iccid] = {}
            interfacesMap[iccid]["pingRowsFinished"], interfacesMap[iccid]["metaRowsFinished"] = False, False
            interfacesMap[iccid]["avgRtt"], interfacesMap[iccid]["avgRssi"] = 0, 0

            # Retrieve the RTT rows and grab the first row
            interfacesMap[iccid]["pingRows"] = session.execute(
                "SELECT nodeid, iccid, timestamp, rtt FROM monroe_exp_ping WHERE nodeid = '" + str(
                    resource['id']) + "' AND iccid = '" + str(interface['iccid']) + "' AND timestamp >= " + str(
                    args.startTimeStamp) + " AND timestamp <= " + str(args.endTimeStamp) + " ALLOW FILTERING",
                timeout=20000)
            interfacesMap[iccid]["pingIterator"] = iter(interfacesMap[iccid]["pingRows"])
            try:
                interfacesMap[iccid]["pingRow"] = interfacesMap[iccid]["pingIterator"].next()
            except Exception:
                interfacesMap[iccid]["pingRowsFinished"] = True

            # Retrieve the RSSI rows and grab the first row
            interfacesMap[iccid]["metaRows"] = session.execute(
                "SELECT nodeid, iccid, timestamp, rssi FROM monroe_meta_device_modem WHERE nodeid = '" + str(
                    resource['id']) + "' AND iccid = '" + str(interface['iccid']) + "' AND timestamp >= " + str(
                    args.startTimeStamp) + " AND timestamp <= " + str(args.endTimeStamp) + " ALLOW FILTERING",
                timeout=20000)
            interfacesMap[iccid]["metaIterator"] = iter(interfacesMap[iccid]["metaRows"])
            try:
                interfacesMap[iccid]["metaRow"] = interfacesMap[iccid]["metaIterator"].next()
            except Exception:
                interfacesMap[iccid]["metaRowsFinished"] = True

        # Initialize the running time to the initial time. At the end of each iteration of the while loop below the
        # running time will be advances by 5
        runningTime = initialTime



        while runningTime <= args.endTimeStamp:
            # Advance through the gps values and find the last position prior to the running time
            # print("gpsRowsFinished: {}, gpsRow.timestamp: {:f}, gpsRow.runningTime: {:f}".format(str(gpsRowsFinished), gpsRow.timestamp, runningTime) )
            while not gpsRowsFinished and gpsRow.timestamp <= runningTime:
                try:
                    utmZone = FindUtmZone(gpsRow.longitude, gpsRow.latitude)
                    p = Proj(proj='utm', zone=utmZone, ellps='WGS84')  # use kwargs
                    x, y = p(gpsRow.longitude, gpsRow.latitude)

                    # Print the row for verification purposes
                    if args.verbose:
                       print ( "node: {} GPS, time: {:f}, zone: {}, x: {:f}, y: {:f} ".format(gpsRow.nodeid, gpsRow.timestamp, utmZone, x, y) )

                    gpsRow = gpsIterator.next()
                except Exception:
                    gpsRowsFinished = True
                    break

            # Loop on the interfaces of this resource (Ping experiment and meta data are reported per iccid)
            for interface in resource['interfaces']:
                iccid = interface['iccid']
                interfacesMap[iccid]["totalRtt"], interfacesMap[iccid]["numOfRttValues"] = 0, 0

                while not interfacesMap[iccid]["pingRowsFinished"] and interfacesMap[iccid][
                    "pingRow"].timestamp <= runningTime:
                    # print("interfacesMap[iccid][pingRowsFinished]: {}, interfacesMap[iccid][pingRow].timestamp: {:f}, runningTime: {:f}".format(interfacesMap[iccid]["pingRowsFinished"], interfacesMap[iccid]["pingRow"].timestamp, runningTime) )
                    try:
                        if interfacesMap[iccid]["pingRow"].rtt is not None:
                            interfacesMap[iccid]["totalRtt"] += interfacesMap[iccid]["pingRow"].rtt
                            interfacesMap[iccid]["numOfRttValues"] += 1

                            # Print the row for verification purposes
                            if args.verbose:
                                print ( "node: {} RTT, iccid: {}, time: {:f}, rtt: {:f}".format(str(interfacesMap[iccid]["pingRow"].nodeid), str(interfacesMap[iccid]["pingRow"].iccid), interfacesMap[iccid]["pingRow"].timestamp, interfacesMap[iccid]["pingRow"].rtt) )

                        interfacesMap[iccid]["pingRow"] = interfacesMap[iccid]["pingIterator"].next()
                    except Exception:
                        break

                interfacesMap[iccid]["totalRssi"], interfacesMap[iccid]["numOfRssiValues"] = 0, 0
                while not interfacesMap[iccid]["metaRowsFinished"] and interfacesMap[iccid][
                    "metaRow"].timestamp <= runningTime:
                    try:
                        if interfacesMap[iccid]["metaRow"].rssi is not None:
                            interfacesMap[iccid]["totalRssi"] += interfacesMap[iccid]["metaRow"].rssi
                            interfacesMap[iccid]["numOfRssiValues"] += 1

                            # Print the row for verification purposes
                            if args.verbose:
                                print ( "node: {} RSSI, iccid: {}, time: {:f}, rssi: {:f}".format(interfacesMap[iccid]["metaRow"].nodeid, interfacesMap[iccid]["metaRow"].iccid, interfacesMap[iccid]["metaRow"].timestamp, interfacesMap[iccid]["metaRow"].rssi))

                        interfacesMap[iccid]["metaRow"] = interfacesMap[iccid]["metaIterator"].next()
                    except Exception:
                        break

            # Print the final results
            #print("node: {}, time: {:f}, x: {:f}, y: {:f} ".format(resource['id'], runningTime, x, y), end='')

            line2write = "node: {} RSSI, iccid: {}, time: {:f}, rssi: {:f}".format(interfacesMap[iccid]["metaRow"].nodeid,
                                                                            interfacesMap[iccid]["metaRow"].iccid,
                                                                            interfacesMap[iccid]["metaRow"].timestamp,
                                                                            interfacesMap[iccid]["metaRow"].rssi)

            #line2write = "node: {}, time: {:f}, x: {:f}, y: {:f} ".format(resource['id'], runningTime, x, y)


            print(line2write)
            writeFile.write(line2write)#+os.linesep)#+'\n')
            #writeFile.write("\n")





            for interface in resource['interfaces']:
                iccid = interface['iccid']

                if interfacesMap[iccid]["numOfRttValues"] > 0:
                    interfacesMap[iccid]["avgRtt"] = interfacesMap[iccid]["totalRtt"] / interfacesMap[iccid][
                        "numOfRttValues"]

                if interfacesMap[iccid]["numOfRssiValues"] > 0:
                    interfacesMap[iccid]["avgRssi"] = interfacesMap[iccid]["totalRssi"] / interfacesMap[iccid][
                        "numOfRssiValues"]

                    #print(", {} rtt: {:f} ({:d} items), {} rssi: {:f} ({:d} items)".format(iccid, interfacesMap[iccid]["avgRtt"], interfacesMap[iccid]["numOfRttValues"], iccid, interfacesMap[iccid]["avgRssi"], interfacesMap[iccid]["numOfRssiValues"]), end='')

                    line2write =", {} rtt: {:f} ({:d} items), {} rssi: {:f} ({:d} items)".format(iccid, interfacesMap[iccid]["avgRtt"], interfacesMap[iccid]["numOfRttValues"], iccid, interfacesMap[iccid]["avgRssi"], interfacesMap[iccid]["numOfRssiValues"])#, end=''

                    print(line2write)
                    writeFile.write(line2write)#+os.linesep)#+'\n')
                    writeFile.write("\n")

            print()
            if args.verbose:
                print("---" + str(runningTime) + "-----")

            runningTime += step
            # sys.exit()



    cluster.shutdown

