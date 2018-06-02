Libraries needed
- cassandra-driver (http://datastax.github.io/python-driver/installation.html)
- pyproj (https://pypi.python.org/pypi/pyproj)
- requests (http://docs.python-requests.org/en/master/user/install/)

Cassandra Instructions

Use your RSA key to access the server: 
ssh-agent # (Or use the -I flag with the ssh command directly)
ssh-add your-key # (Or use the -I flag with the ssh command directly)

ssh-add public_key

ssh -p 2280 -N -L9042:127.0.0.1:9042 monroedb@163.117.140.155 


The last command opens a tunnel to our server so that you can access the DB thru port 9042 on YOUR machine. That is, port 9042 in your machine is redirected to port 9042 in the server (port 9042 is NOT --should not be-- directly accessible in the server from outside). 
The command requests (-N) a no-shell session (the user can't establish a session), so it will remain open until you press ctrl-c


usage: fetchMonroeData.py [-h] -p PROJECT -s STARTTIME -e ENDTIME [-v]
                          [-i INTERVAL] -c CERTIFICATE -k PRIVATEKEY

GPS to x-y coordinate mapper and row aggregator

optional arguments:
  -h, --help            show this help message and exit
  -p PROJECT, --project PROJECT
                        Project to retrieve data for
  -s STARTTIME, --startTime STARTTIME
                        Starting timestamp
  -e ENDTIME, --endTime ENDTIME
                        Ending timestamp
  -v, --verbose         Display individual rows
  -i INTERVAL, --interval INTERVAL
                        Aggregation interval in seconds (default = 5)
  -c CERTIFICATE, --certificate CERTIFICATE
                        Path to the client certificate used for server
                        authentication
  -k PRIVATEKEY, --privateKey PRIVATEKEY
                        Path to the private key used for server authentication

project: choose between: Spain, Norway, Sweden, Italy
starttime: date to begin, e.g. '2017-10-27 16:35'
endtime: ending time/date
v: verbose: will show all records which will be combined eventually
i: aggregation interval. It is five (5) secs by default.
c: τοpath to the certificate for client authentication
k: the key for client authentication

examples: 
python3 ./fetchMonroeData.py -p Spain -i 60 -s '2015-01-01 16:35' -e '2017-01-01 16:35' -c "./certificate.pem" -k "./privateKeyClear.pem"

python3 ./fetchMonroeDataOnlyGPSnodes.py -v -p sweden -i 5 -s '2018-01-01 11:59' -e '2018-01-09 11:59' -c ./certificate.pem -k ./privateKeyClear.pem
