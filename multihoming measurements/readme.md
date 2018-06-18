
# Experiment
This is an adaptation of the original ping script by Jonas Karlsson. The original
script takes a single interface and runs the ping experiment on that interface.
This script takes a list of interfaces and runs the experiments on all those
interfaces. The idea is to measure RTT on all available interfaces and ultimately
be able to select which interface to use for outgoing traffic.
The experiments measure IP RTT by continuously send ping
packets to a configurable server (default 195.251.209.199 - swn.uom.gr).

The experiment will send 1 Echo Request (ICMP type 8) packet per second to a
server over all specified interfaces until aborted.
RTT is measured as the time between the Echo request and the Echo reply
(ICMP type 0) is received from the server.

The experiment is designed to run as a docker container and will not attempt to
do any active network configuration.
If the Interface does not exist (ie is not UP) when the experiment starts it
will immediately exit.

The default values are (can be overridden by a /monroe/config):
```
{
      "guid": "no.guid.in.config.file",  # Should be overridden by scheduler
      "zmqport": "tcp://172.17.0.1:5556",
      "nodeid": "fake.nodeid",
      "modem_metadata_topic": "MONROE.META.DEVICE.MODEM",
      "server": "195.251.209.199",  # default ping target (swn.uom.gr)
      "interval": 5000,  # time in milliseconds between successive packets
      "dataversion": 2,
      "dataid": "MONROE.EXP.UOMPING",
      "meta_grace": 120,  # Grace period to wait for interface metadata
      "ifup_interval_check": 5,  # Interval to check if interface is up
      "export_interval": 5.0,
      "verbosity": 2,  # 0 = "Mute", 1=error, 2=Information, 3=verbose
      "resultdir": "/monroe/results/",
      "modeminterfacename": "InternalInterface",
      "interfacenames": ["op0", "op1"]  # Interfaces to run the experiment on
      "interfaces_without_metadata": ["eth0",
                                      "wlan0"]  # Manual metadata on these IF
}
```
All debug/error information will be printed on stdout
depending on the "verbosity" variable.

## Requirements

These directories and files must exist and be read/writable by the user/process
running the container.
/monroe/config
"resultdir" (from /monroe/config see defaults above)    


## The experiment will execute a statement similar to running fping like this
```bash
fping -I op0 -D -p 5000 -l 195.251.209.199
```

## Sample output
The experiment will produce a single line JSON object similar to these (pretty printed and added comments here for readability)
### Succesful reply
```
 {
   "Guid": "313.123213.123123.123123", # exp_config['guid']
   "Timestamp": 23123.1212, # time.time()
   "Iccid": 2332323, # meta_info["ICCID"]
   "Operator": "Telia", # meta_info["Operator"]
   "NodeId" : "9", # exp_config['nodeid']
   "DataId": "MONROE.EXP.PING",
   "DataVersion": 2,
   "SequenceNumber": 70,
   "Rtt": 6.47,
   "Bytes": 84,
   "Host": "8.8.8.8",
 }
```
### No reply (lost interface or network issues)
```
 {
   "Guid": "313.123213.123123.123123", # exp_config['guid']
   "Timestamp": 23123.1212, # time.time()
   "Iccid": 2332323, # meta_info["ICCID"]
   "Operator": "Telia", # meta_info["Operator"]
   "NodeId" : "9", # exp_config['nodeid']
   "DataId": "MONROE.EXP.PING",
   "DataVersion": 2,
   "SequenceNumber": 70,
   "Host": "8.8.8.8",
 }
```



# Multi-homing experiment in detail
Our multi-homing experiment script includes the following options (combined EXPCONFIG options of the ping and http_download experiments):
```
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
```
Most of these options are either part of the “ping” or the “http_download” experiments. The “pingTarget” in the multi-homing experiment is used for all interfaces and the “interfacenames” option determines the interfaces that the fping command will be run on. Also, the “resultfile” is the output file where all the output of the fping and curl commands will be written.
The script also reads a configuration file with the relative time, repetitions and URL for each action. A sample of this file is shown below:
```
CURL_EXPCONFIG = {
    "Actions": [
        { "Time": 10, "Repetitions": 2, "Url": "http://www.google.com/" },
        { "Time": 20, "Repetitions": 1, "Url": "http://www.uom.gr/" },
        { "Time": 30, "Repetitions": 4, "Url": "http://www.bbc.com/" },
        { "Time": 35, "Repetitions": 3, "Url": "http://www.dictionary.com/" }
    ]
}
```
At the start of the script execution the starting time is recorded. All “Time” entries in the actions configuration file will be interpreted relative to the recorded starting time. 
The run_ping_exp function, which is run in a separate process, is very similar to the corresponding function of the provided ping experiment. The only differences are that this run_ping_exp function adds the resulting RTT to a list shared by all the processes and that it appends the experiment output to a log list. The list holds the output for all commands run by the experiment and is dumped to the results file when all actions have finished executing. Thus, the experiment follows the MONROE best practice of not writing to the results directory (which is continuously synchronized), during the experiment.
The run_curl_exp function is executed in a separate process every few seconds and checks if there are any pending actions to be executed (i.e. actions for which the time has been reached). For each such action, the script calculates the average RTT for all interfaces and selects the interface with the lowest RTT value. The script also marks the selected actions as executed. The curl command to download the specified URL is run as many times as specified in the “Repetitions” part of the action over the selected interface (dynamic execution) and then again, the same number of times, over the interface that appears first in the interfaces list (static execution). Static execution is used in order to demonstrate the effectiveness of the dynamic method. As with the fping command, the output of the curl command is saved in the log list in order to be written to the results file in the end of the script execution.
Several other functions that are part of the mulit-homing experiment are also part of the MONROE example experiments and, so they will not be presented here. We have also created a number of new housekeeping functions in order to coordinate the metadata listening processes. Since our experiment operates on multiple interfaces a different metadata process is started for each interface. As per the provided MONROE experiment samples, the script will start sending data only after metadata for all interfaces have been received. 
The main part of the Python script that constitutes the multi-homing experiment starts by reading the primary and download action configuration files. Once the action in the action configuration file are read into memory they are tagged as not-executed. A number of data structures are then created in order to hold information related to the experiment. For instance, the script needs to store for each interface information related to the metadata, the metadata process, the ping command process and the RTT list. The curl process information is stored in a scalar variable as there is only one for the entire experiment.
After the initial setup, the script enters an infinite loop and sleeps for a configurable time (default is 5 seconds) at the end of the loop. If any of the metadata processes is dead all metadata processes and ping process are recreated and started (along the same lines as the original ping experiment). The curl process is also recreated and restarted. Then, the script checks if all ping processes and the curl process are up and running and, if not, they are restarted. Finally, it is checked whether all actions have been executed in which case all processes are terminated and the contents of the log list (the list with all the experiment output) is written to the results file.
In order to demonstrate the multi-homing script we ran a sample experiment on node 428 of the Vtab buses project in Sweden. The node has two mobile interfaces one with operator “3” and the other with operator “Telia”. The first operator (“3”) is used by the static method while the dynamic method dynamically selects between the two as described above. The experiment ran for about 4 minutes and executed the following actions:
```
        { "Time": 20, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 30, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 40, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 50, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 60, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 70, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 80, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 90, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 100, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 110, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 120, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 130, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 140, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 150, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 160, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 170, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 180, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 190, "Repetitions": 5, "Url": "http://www.bbc.com/" },
        { "Time": 200, "Repetitions": 5, "Url": "http://www.bbc.com/" }
```
The BBC website was downloaded five times every 10 seconds starting at time 20 seconds from the experiment start for each of the dynamic and static interface selection. The BBC website was selected as its first page was relatively large at 200 KB. A separate Python script parsed the JSON objects in the results file and produced the final results, which were imported into an Excel file.
The chart below displays the download speeds for the dynamic and static interface selection scenarios as well as the recent average RTTs for the two mobile operators of the node (“3” and “Telia”). The x axis represents seconds since the beginning of the experiment. The static interface selection always downloads the web pages using operator “3”. The dynamic download starts with using “Telia” which in the beginning has a lower RTT measurement. At around time 5 seconds the dynamic selection switches to operator “3” as the “Telia” RTT becomes very high. Finally, the dynamic selection switches to “Telia” at approximately time 36 seconds and remains with “Telia” for the rest of the experiment. It is can be observed that the dynamic selection results in higher download speed for most downloads.

![download speed for dynamic and static interface selection](https://user-images.githubusercontent.com/16095622/41564046-4dbec33c-735a-11e8-9802-9bed7b8bc6ef.png)
###Download speed for dynamic and static interface selection and RTT for "3” and “Telia” mobile operators
Please note that the above results are by no means complete. Further experimentation is necessary in order to produce significant results. Besides, the interface selection at the moment is rudimentary and so it does not exhibit considerable scientific interest. However, by developing this script we have set the basis for conducting various much more interesting experiments in the future.

