#!/usr/bin/python
# -*- coding: utf-8 -*-

# Author: Dimitris Vardalis (based on the original script by Jonas Karlsson)
# Date: January 2018
# License: GNU General Public License v3
# Developed for use by the EU H2020 MONROE project

"""
This is an adaptation of the original ping script by Jonas Karlsson. The original
script takes a single interface and runs the ping experiment on that interface.
This script takes a list of interfaces and runs the experiments on all those
interfaces. The idea is to measure RTT on all available interfaces and ultimately
be able to select which interface to use for outgoing traffic.

The script will run forever on all specified interfaces.
All default values are configurable from the scheduler.
"""
import zmq
import json
import sys
from multiprocessing import Process, Manager
import subprocess
import netifaces
import re
import time
import signal
import monroe_exporter
import io
from subprocess import check_output, CalledProcessError
import datetime

# Configuration
DEBUG = False
CONFIGFILE = '/monroe/config'
CURL_CONFIGFILE = '/opt/monroe/curl_config'

# Default values (overwritable from the scheduler)
# Can only be updated from the main thread and ONLY before any
# other processes are started
EXPCONFIG = {
        "guid": "no.guid.in.config.file",  # Should be overridden by scheduler
        "zmqport": "tcp://172.17.0.1:5556",
        "nodeid": "fake.nodeid",
        "modem_metadata_topic": "MONROE.META.DEVICE.MODEM",
        "pingTarget": "195.251.209.199",  # default ping target (swn.uom.gr)
        "interval": 5000,  # time in milliseconds between successive packets
        "dataversion": 2,
        "dataid": "MONROE.EXP.UOMPING.PING",
        "dataidCurl": "MONROE.EXP.UOMPING.CURL",
        "meta_grace": 120,  # Grace period to wait for interface metadata
        "ifup_interval_check": 5,  # Interval to check if interface is up
        "export_interval": 5.0,
        "verbosity": 0,  # 0 = "Mute", 1=error, 2=Information, 3=verbose
        "resultdir": "/monroe/results/",
        "resultfile": "/monroe/results/results.txt",
        "modeminterfacename": "InternalInterface",
        "interfacenames": ["op0", "op1"],  # Interfaces to run the experiment on
        "interfaces_without_metadata": ["eth0", "wlan0"],  # Manual metadata on these IF
        "size": 3*1024,  # The maximum size in Kbytes to download
        "time": 3600  # The maximum time in seconds for a download
        }

# Sample curl experiment config file. Will be overwritten by the configuration file.
CURL_EXPCONFIG = {
    "Actions": [
        { "Time": 10, "Repetitions": 2, "Url": "http://www.google.com/" },
        { "Time": 20, "Repetitions": 1, "Url": "http://www.uom.gr/" },
        { "Time": 30, "Repetitions": 4, "Url": "http://www.bbc.com/" },
        { "Time": 35, "Repetitions": 3, "Url": "http://www.dictionary.com/" }
    ]
}

# What to save from curl
CURL_METRICS = ('{ '
                '"Host": "%{remote_ip}", '
                '"Port": "%{remote_port}", '
                '"Speed": %{speed_download}, '
                '"Bytes": %{size_download}, '
                '"Url": "%{url_effective}", '
                '"TotalTime": %{time_total}, '
                '"SetupTime": %{time_starttransfer} '
                '}')

# The side of the sliding window that will store the latest RTT measurements
WINDOW_SIZE = 10

# Starting datetime - helps in keeping track of the relative execution times for the curl experiment
START_DATETIME = datetime.datetime.now()

def run_ping_exp(my_interface_map, expconfig, log_list):
    global FPING_PROCESS

    meta_info = my_interface_map['meta_info']
    rtts = my_interface_map['rtts']
    rssis = my_interface_map['rssis']
    
    # Set some variables for saving data every export_interval
    monroe_exporter.initalize(expconfig['export_interval'],
                              expconfig['resultdir'])

    ifname = meta_info[expconfig["modeminterfacename"]]
    interval = float(expconfig['interval']/1000.0)
    pingTarget = expconfig['pingTarget']
    cmd = ["fping",
           "-I", ifname,
           "-D",
           "-c", "1",
           pingTarget]
    # Regexp to parse fping ouput from command
    r = re.compile(r'^\[(?P<ts>[0-9]+\.[0-9]+)\] (?P<host>[^ ]+) : \[(?P<seq>[0-9]+)\], (?P<bytes>\d+) bytes, (?P<rtt>[0-9]+(?:\.[0-9]+)?) ms \(.*\)$')

    # This is the inner loop where we wait for output from fping
    # This will run until we get a interface hickup, where the process will be
    # killed from parent process.
    seq = 0
    while True:
        popen = subprocess.Popen(cmd,
                                 stdout=subprocess.PIPE,
                                 bufsize=1)
        output = popen.stdout.readline()
        m = r.match(output)
        if m is not None:  # We could send and got a reply
            # keys are defined in regexp compilation. Nice!
            exp_result = m.groupdict()
            
            # Add RTT and RSSI values to the relevant lists (aka windows)
            add_value(rtts, float(exp_result['rtt']))
            add_value(rssis, meta_info["RSSI"])
            
            msg = {
                            'Bytes': int(exp_result['bytes']),
                            'Host': exp_result['host'],
                            'Rtt': float(exp_result['rtt']),
                            'AvgRtt': calc_avg(rtts),
                            'SequenceNumber': int(seq),
                            'Timestamp': float(exp_result['ts']),
                            "Guid": expconfig['guid'],
                            "DataId": expconfig['dataid'],
                            "Interface": ifname,                            
                            "DataVersion": expconfig['dataversion'],
                            "NodeId": expconfig['nodeid'],
                            "Iccid": meta_info["ICCID"],
                            "Operator": meta_info["Operator"],
                            "Rssi": meta_info["RSSI"],
                            "AvgRssi": calc_avg(rssis),
                  }

        else:  # We lost the interface or did not get a reply
            msg = {
                            'Host': pingTarget,
                            'SequenceNumber': int(seq),
                            'Timestamp': time.time(),
                            "Guid": expconfig['guid'],
                            "DataId": expconfig['dataid'],
                            "Interface": ifname,
                            "DataVersion": expconfig['dataversion'],
                            "NodeId": expconfig['nodeid'],
                            "Iccid": meta_info["ICCID"],
                            "Operator": meta_info["Operator"]
                   }

        if expconfig['verbosity'] > 2:
            print msg
        if not DEBUG:
            # We have already initalized the exporter with the export dir
            monroe_exporter.save_output(msg)
            log_list.append(unicode(json.dumps(msg) + '\n'))
            # with io.open(expconfig['resultfile'], 'a') as f:
            #    f.write(unicode(json.dumps(msg) + '\n'))

        seq += 1
        # Sleep for the predefined interval and re-execute loop
        time.sleep(interval)
    # Cleanup
    if expconfig['verbosity'] > 1:
        print "Cleaning up fping process"
    popen.stdout.close()
    popen.terminate()
    popen.kill()

def run_curl_exp(interfacesMap, expconfig, curl_config, log_list):
    # Create a local copy of the actions key of the config dictionary
    # The local copy will be changed and then re-assigned to the multiprocessing
    # proxy so that the shared data structure is updated
    local_actions = curl_config['Actions']
    
    # Find next action. If no action is found action will be None
    action = find_next_action(local_actions, expconfig)

    while action is not None:
        selectedInterface = None
        minRtt = -1
        
        # Loop through all available interface, calculate the average RTT for each and
        # find the interface with the smallest RTT. Only consider interfaces with at least
        # one measurement
        for interface, value in interfacesMap.iteritems():
            interfaceAvg = calc_avg(interfacesMap[interface]['rtts'])
            if interfaceAvg > -1:
                if selectedInterface is None:
                    selectedInterface = interface
                    minRtt = interfaceAvg
                elif interfaceAvg < minRtt:
                    selectedInterface = interface
                    minRtt = calc_avg(interfacesMap[interface]['rtts'])

            if selectedInterface is None and expconfig['verbosity'] > 1:
                print "No RTT data. Curl action aborted"
                return

        if expconfig['verbosity'] > 1:
            print "Selected interface is " + selectedInterface
       
        executeAction(action, selectedInterface, expconfig, log_list, True)
        
        for interface, value in interfacesMap.iteritems():
            selectedInterface = interface
            break;
        
        executeAction(action, selectedInterface, expconfig, log_list, False)
        
        # Mark action as executed
        action['IsExecuted'] = True
        # Re-assign the dictionary to the proxy
        curl_config['Actions'] = local_actions
        # Re-assign the actions dictionary to the local variable (not sure if it is necessary)       
        local_actions = curl_config['Actions']
        
        # Get the next action
        action = find_next_action(local_actions, expconfig)

def executeAction(action, selectedInterface, expconfig, log_list, dynamicSelection):
    meta_info = interfacesMap[selectedInterface]['meta_info']
    rssis = interfacesMap[selectedInterface]['rssis']
    rtts = interfacesMap[selectedInterface]['rtts']

    ifname = meta_info[expconfig["modeminterfacename"]]
    interval = float(expconfig['interval']/1000.0)

    cmd = ["curl",
           "-o", "/dev/null",  # to not output filecontents on stdout
           "--fail",  # to get the curl exit code 22 for http failures
           "--insecure",  # to allow selfsigned certificates
           "--raw",
           "--silent",
           "--write-out", "{}".format(CURL_METRICS),
           "--interface", "{}".format(ifname),
           "--max-time", "{}".format(expconfig['time']),
           # "--range", "0-{}".format(expconfig['size'] - 1),
           "{}".format(action['Url'])]

    # Safeguard to always have a defined output variable
    output = None
    
    # Iterate over the number of repetitions for the current action
    for i in range(0, action['Repetitions']):
        err_code = 0
        try:
            start_curl = time.time()
            try:
                output = check_output(cmd)
            except CalledProcessError as e:
                    err_code = e.returncode # AEL get the error code here
                    output = e.output
                    # if e.returncode == 28:  # time-limit exceeded
                    #     if expconfig['verbosity'] > 2:
                    #         print ("Exceding timelimit {}, "
                    #                "saving what we have").format(expconfig['time'])
                    #     output = e.output
                    # else:
                    #     raise e
            # Clean away leading and trailing whitespace
            output = output.strip(' \t\r\n\0')
            # Convert to JSON
            msg = json.loads(output)
            msg.update({
                "ErrorCode": err_code,
                "Guid": expconfig['guid'],
                "DataId": expconfig['dataidCurl'],
                "DataVersion": expconfig['dataversion'],
                "NodeId": expconfig['nodeid'],
                "Timestamp": start_curl,
                "Iccid": meta_info["ICCID"],
                "Operator": meta_info["Operator"],
                "DownloadTime": msg["TotalTime"] - msg["SetupTime"],
                "SequenceNumber": i
            })
            
            if dynamicSelection:
                msg.update({ "DynamicSelection": True })
            else:
                msg.update({ "DynamicSelection": False })
            
            if expconfig['verbosity'] > 2:
                print msg
            if not DEBUG:
                monroe_exporter.save_output(msg, expconfig['resultdir'])
                log_list.append(unicode(json.dumps(msg) + '\n'))
        except Exception as e:
            if expconfig['verbosity'] > 0:
                print ("Execution or parsing failed for "
                       "command : {}, "
                       "output : {}, "
                       "error: {}").format(cmd, output, e)

def metadata(meta_ifinfo, ifname, expconfig):
    """Seperate process that attach to the ZeroMQ socket as a subscriber.

        Will listen forever to messages with topic defined in topic and update
        the meta_ifinfo dictionary (a Manager dict).
    """
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(expconfig['zmqport'])
    socket.setsockopt(zmq.SUBSCRIBE, expconfig['modem_metadata_topic'])
    # End Attach
    while True:
        data = socket.recv()
        try:
            ifinfo = json.loads(data.split(" ", 1)[1])
            if (expconfig["modeminterfacename"] in ifinfo and
                    ifinfo[expconfig["modeminterfacename"]] == ifname):
                # In place manipulation of the reference variable
                for key, value in ifinfo.iteritems():
                    meta_ifinfo[key] = value
        except Exception as e:
            if expconfig['verbosity'] > 0:
                print ("Cannot get modem metadata in http container"
                       "error : {} , {}").format(e, expconfig['guid'])
            pass


# Helper functions could be moved to monroe_utils
def check_if(ifname):
    """Check if interface is up and have got an IP address."""
    return (ifname in netifaces.interfaces() and
            netifaces.AF_INET in netifaces.ifaddresses(ifname))


def check_meta(info, graceperiod, expconfig):
    """Check if we have received required information within graceperiod."""
    return (expconfig["modeminterfacename"] in info and
            "Operator" in info and
            "Timestamp" in info and
            time.time() - info["Timestamp"] < graceperiod)


def add_manual_metadata_information(info, ifname, expconfig):
    """Only used for local interfaces that do not have any metadata information.

       Normally eth0 and wlan0.
    """
    info[expconfig["modeminterfacename"]] = ifname
    info["ICCID"] = ifname
    info["Operator"] = ifname
    info["Timestamp"] = time.time()


def create_meta_process(ifname, expconfig):
    """Create a meta process and a shared dict for modem metadata state."""
    meta_info = Manager().dict()
    process = Process(target=metadata,
                      args=(meta_info, ifname, expconfig, ))
    process.daemon = True
    return (meta_info, process)


def create_ping_exp_process(my_interface_map, expconfig, log_list):
    """This create a ping experiment thread."""
    process = Process(target=run_ping_exp, args=(my_interface_map, expconfig, log_list, ))
    process.daemon = True
    return process

def create_curl_exp_process(interfaces_map, expconfig, curlconfig, log_list):
    """This create a curl experiment thread."""
    process = Process(target=run_curl_exp, args=(interfaces_map, expconfig, curlconfig, log_list, ))
    process.daemon = True
    return process

def any_meta_dead(expconfig, interfacesMap):
    """Is any meta process not running?"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check

    for ifname in ifnames:
        if not interfacesMap[ifname]['meta_process'].is_alive():
            return True
    return False

def start_dead_meta(expconfig, interfacesMap):
    """Start meta processes that are not running"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check

    for ifname in ifnames:
        if not interfacesMap[ifname]['meta_process'].is_alive():
            interfacesMap[ifname]['meta_info'], interfacesMap[ifname]['meta_process'] = create_meta_process(ifname, expconfig)
            interfacesMap[ifname]['meta_process'].start()
            if interfacesMap[ifname]['ping_exp_process'].is_alive():  # Clean up the exp_thread
                interfacesMap[ifname]['ping_exp_process'].terminate()

def add_ifs_metadata(expconfig, interfacesMap):
    """Add metadata to all applicable interfaces"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check
    if_without_metadata = expconfig['interfaces_without_metadata']
    for ifname in ifnames:
        # On these Interfaces we do net get modem information so we hack
        # in the required values by hand which will immediately terminate
        # metadata loop below
        if (check_if(ifname) and ifname in if_without_metadata):
            add_manual_metadata_information(interfacesMap[ifname]['meta_info'], ifname, expconfig)

def all_ifs_are_up(expconfig, interfacesMap):
    """Check if all interfaces are up"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check
    for ifname in ifnames:
        # Do we have the interfaces up ?
        if not (check_if(ifname) and check_meta(interfacesMap[ifname]['meta_info'], meta_grace, expconfig)):    
            return False
    return True

def all_exp_completed(expconfig, interfacesMap):
    """Check if all exp processes have completed"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check

    for ifname in ifnames:
        if interfacesMap[ifname]['ping_exp_process'].is_alive():
            return False
    return True
    
def start_all_exp(expconfig, interfacesMap):
    """Start all exp processes. If any is still running kill it first"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check
    
    for ifname in ifnames:
        # Do we have the interfaces up ?
        if (check_if(ifname) and check_meta(interfacesMap[ifname]['meta_info'], meta_grace, expconfig)):
            # We are all good
            if expconfig['verbosity'] > 2:
                print "Interface {} is up".format(ifname)
            if interfacesMap[ifname]['ping_exp_process'].is_alive():
                interfacesMap[ifname]['ping_exp_process'].terminate()
            interfacesMap[ifname]['ping_exp_process'].start()

def recreate_all_exp(expconfig, interfacesMap, log_list):
    """Recreate all experiment processes"""
    ifnames = expconfig['interfacenames'] # List of interfaces to check
    if_without_metadata = expconfig['interfaces_without_metadata']
    
    meta_grace = expconfig['meta_grace']
    for ifname in ifnames:
        if interfacesMap[ifname]['ping_exp_process'].is_alive():
            if expconfig['verbosity'] > 2:
                print ("Interface {} is down and "
                       "experiment are running").format(ifname)
            # Interfaces down and we are running
            interfacesMap[ifname]['ping_exp_process'].terminate()
        interfacesMap[ifname]['ping_exp_process'] = create_ping_exp_process(interfacesMap[ifname], expconfig, log_list)

def add_value(window, value):
    """Add new value to a window"""
    if len(window) < WINDOW_SIZE:
        window.insert(0, value)
    else:
        window.pop()
        window.insert(0, value)

def calc_avg(window):
    """Calculate average for the given window"""
    runningSum = 0.0
    for x in window:
        runningSum += x
    if len(window) > 0:
        return runningSum / len(window)
    return -1

def find_next_action(curl_actions, expconfig):
    currentTime = datetime.datetime.now()
    
    if expconfig['verbosity'] > 1:
        for action in curl_actions:
            print action['Time']
            print action['Repetitions']
            print action['Url']
            print action['IsExecuted']
            print '------------------'
    
    # Find the first action with a Time less than or equal to the current time
    for action in curl_actions:
        # Convert relative action time to absolute based on the START_DATETIME set at the
        # experiment start
        eventTime = START_DATETIME + datetime.timedelta(0, action['Time'])
        if not action['IsExecuted'] and eventTime <= currentTime:
            return action;
    
    return None

def all_actions_executed(curl_actions):
    # Check if all actions are executed
    for action in curl_actions:
        if not action['IsExecuted']:
            return False;

    return True

if __name__ == '__main__':
    """The main thread control the processes (experiment/metadata)."""
    
    if not DEBUG:
        import monroe_exporter
        # Try to get the experiment config as provided by the scheduler
        try:
            with open(CONFIGFILE) as configfd:
                EXPCONFIG.update(json.load(configfd))
        except Exception as e:
            print "Cannot retrieve expconfig {}".format(e)
            raise e
            
        # Try to get the curl experiment config
        try:
            curl_config = Manager().dict()
            with open(CURL_CONFIGFILE) as curl_configfd:
                CURL_EXPCONFIG = json.load(curl_configfd)
        except Exception as e:
            print "Cannot retrieve expconfig {}".format(e)
            raise e
        
        if EXPCONFIG['verbosity'] > 1:
            print "Falsifying..."

        for action in CURL_EXPCONFIG['Actions']:
            action['IsExecuted'] = False

        curl_config.update(CURL_EXPCONFIG)
        
    else:
        # We are in debug state always put out all information
        EXPCONFIG['verbosity'] = 3

    # Short hand variables and check so we have all variables we need
    try:
        ifnames = EXPCONFIG['interfacenames'] # List of interfaces to run the experiment on
        if_without_metadata = EXPCONFIG['interfaces_without_metadata']
        meta_grace = EXPCONFIG['meta_grace']
        ifup_interval_check = EXPCONFIG['ifup_interval_check']
        EXPCONFIG['guid']
        EXPCONFIG['modem_metadata_topic']
        EXPCONFIG['zmqport']
        EXPCONFIG['nodeid']
        EXPCONFIG['verbosity']
        EXPCONFIG['resultdir']
        EXPCONFIG['export_interval']
        EXPCONFIG['modeminterfacename']
    except Exception as e:
        print "Missing expconfig variable {}".format(e)
        raise e

    if EXPCONFIG['verbosity'] > 2:
        print EXPCONFIG

    # Create a shared list to store logs
    log_list = Manager().list()

    interfacesMap = {}
    
    for ifname in ifnames:
        # Create a map to hold information relevant to this interface
        interfacesMap[ifname] = {}
        # Create a process for getting the metadata
        interfacesMap[ifname]['meta_info'], interfacesMap[ifname]['meta_process'] = create_meta_process(ifname, EXPCONFIG)
        interfacesMap[ifname]['meta_process'].start()

        # Create an experiment script
        interfacesMap[ifname]['ping_exp_process'] = create_ping_exp_process(interfacesMap[ifname], EXPCONFIG, log_list)
        
        # Initialize value windows
        interfacesMap[ifname]['rtts'] = Manager().list()
        interfacesMap[ifname]['rssis'] = Manager().list()
    
    curl_exp_process = create_curl_exp_process(interfacesMap, EXPCONFIG, curl_config, log_list)
    
    # Control the processes
    while True:
        # If any of the meta is dead restart it and terminate all possible processes that may be still running
        if any_meta_dead(EXPCONFIG, interfacesMap):
            if EXPCONFIG['verbosity'] > 2:
                print "Any meta dead"
            for ifname in ifnames:
                if not interfacesMap[ifname]['meta_process'].is_alive():
                    interfacesMap[ifname]['meta_info'], interfacesMap[ifname]['meta_process'] = create_meta_process(ifname, expconfig)
                    interfacesMap[ifname]['meta_process'].start()
                if interfacesMap[ifname]['ping_exp_process'].is_alive():  # Clean up the exp_thread
                    interfacesMap[ifname]['ping_exp_process'].terminate()
                
                interfacesMap[ifname]['ping_exp_process'] = create_ping_exp_process(interfacesMap[ifname], EXPCONFIG)
            if curl_exp_process.is_alive():
                curl_exp_process.terminate()
            curl_exp_process = create_curl_exp_process(interfacesMap, EXPCONFIG, curl_config, log_list)

        add_ifs_metadata(EXPCONFIG, interfacesMap)

        if all_ifs_are_up(EXPCONFIG, interfacesMap):
            if all_exp_completed(EXPCONFIG, interfacesMap):
                if EXPCONFIG['verbosity'] > 2:
                    print "Starting all exp"
                start_all_exp(EXPCONFIG, interfacesMap)
        else:
            if EXPCONFIG['verbosity'] > 2:
                print "Recreating all exp"
            recreate_all_exp(EXPCONFIG, interfacesMap, log_list)

        if not curl_exp_process.is_alive():
            curl_exp_process = create_curl_exp_process(interfacesMap, EXPCONFIG, curl_config, log_list)
            curl_exp_process.start()
        
        if all_actions_executed(curl_config['Actions']):
            break
        else:
            time.sleep(ifup_interval_check)
            
    for ifname in ifnames:
        interfacesMap[ifname]['meta_process'].terminate()
        interfacesMap[ifname]['ping_exp_process'].terminate()
    curl_exp_process.terminate()
    
    # Output log list entries to file
    with io.open(EXPCONFIG['resultfile'], 'w') as f:
        for log in log_list:
            f.write(log)
