# ===================================================================================== #
# Module for reading data from Axis Neuron broadcast port.
# Author: Eddie Lee edl56@cornell.edu
# ===================================================================================== #
from __future__ import division
import numpy as np
from datetime import datetime,timedelta
import os,time,pause,socket,shutil
import pandas as pd
from load import calc_file_headers

HOST = '127.0.0.1'   # use '' to expose to all networks
PORT = 7003  # Calculation data.

# Functions for reading from broadcasting port.
def read_port():
    def incoming(host, port):
        """Open specified port and return file-like object"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.connect((host,port))
        data=sock.recvfrom(32768)
        sock.close()
        return data[0]
    data = incoming(HOST, PORT)
    return datetime.now(),data

def format_port_output(s):
    s=s.split(' ')[1:11]
    f=[float(i) for i in s]
    return f

def _format_port_output(s):
    """For BVH file."""
    iloc=s.find('Caeli')
    if iloc==-1:
        return ['NaN']*10
    s=s[iloc:].split(' ')[1:11]
    f=[float(i) for i in s]
    return f
# end port section

def record_AN_port(fname):
    """
    Start recording data from Axis Neuron port at some predetermined time and saves it to file name.
    
    Params:
    -------
    fname (str)
    """
    while not os.path.isfile('C:/Users/Eddie/Dropbox/Sync_trials/Data/start.txt'):
        pause.seconds(1)

    data = []  # Port output.
    portOut = [datetime.now()]*2
    startTime = datetime.now()
    max_wait_time = 1000
    while ( (not os.path.isfile('C:/Users/Eddie/Dropbox/Sync_trials/Data/end.txt')) and
            (datetime.now()-startTime).total_seconds()<max_wait_time ):
        portOut = read_port()
        data.append(portOut)
    
    headers = list(calc_file_headers())
    headers[-1] = ''.join(headers[-1].split())  # Remove space in last column header.
    with open(fname,'w') as f:
        f.write('Start time: %s\n'%data[0][0].isoformat())
        f.write('End time: %s\n\n'%data[-1][0].isoformat())
        f.write('Timestamp '+' '.join(headers)+'\n')
        for d in data:
            t = d[0].isoformat()
            #if '\r' in d[1] or '\n' in d[1]:
            #    raise Exception
            f.write('%s %s\n'%(t,d[1].rstrip()))

def _fix_problem_dates(f,fname):
    """
    Insert missing datetime or missing microseconds at beginning of line. Put in 1900-01-01T00:00:00.000 if
    missing date completely.
    """
    import uuid
    tmpfile = str(uuid.uuid4())
    with open('/tmp/'+tmpfile,'w') as fout:
        # skip header lines
        for i in xrange(5):
            fout.write(f.readline())

        for ln in f:
            try:
                d = datetime.strptime(ln[:26], '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                if len(ln[:26].split()[0])==19:
                    # Some values seem to be cutoff because microseconds is precisely 0.
                    #print "Inserting microseconds."
                    ln = ln.split()
                    ln[0] += '.000000'
                    ln = ' '.join(ln)+'\n'
                else:
                    ln = '1900-01-01T00:00:00.000000 '+ln
                # Sometimes, a single port broadcost seems to overlap with another.
                if len(ln.split())>948:
                    ln = ' '.join(ln.split()[:948])+'\n'
            fout.write(ln) 
    shutil.move('/tmp/'+tmpfile,fname)

def load_AN_port(fname,dr='',time_as_dt=True,n_avatars=1,fix_file=True,read_csv_kwargs={}):
    """
    With data from a single individual at this moment.
    
    Params:
    -------
    fname (str)
    dr (str='')
    time_as_dt (bool=True)
    fix_file (bool=True)
        Parse input file and fix any problems with dates.
    """
    if len(dr)>0:
        fname = '%s/%s'%(dr,fname)
    
    if fix_file:
        # Insert missing times for the file to be read in.
        with open(fname,'r') as f:
            _fix_problem_dates(f,fname) 

    # Read in start and stop times at beginning of file.
    #with open(fname,'r') as f:
    #    startTime = datetime.strptime( f.readline().split(' ')[-1] )
    #    stopTime = datetime.strptime( f.readline().split(' ')[-1] )
            
    df = pd.read_csv(fname,delimiter=' ',skiprows=3,**read_csv_kwargs)
    df.iloc[:,0] = df.iloc[:,0].apply(lambda t: datetime.strptime(t, '%Y-%m-%dT%H:%M:%S.%f'))

    # Linearly interpolate missing date times. Assuming that no two sequential data points are missing
    # times which seems to be the case...
    iloc = np.where( pd.DatetimeIndex(df['Timestamp']).year==1900 )[0]
    for i in iloc:
        if i>0 and i<(len(df)-1):
            df.iloc[i,0] = timedelta(seconds=(df.iloc[i+1,0]-df.iloc[i-1,0]).total_seconds()/2) + df.iloc[i-1,0]
    # Remove last data point if the time is uncertain.
    if pd.DatetimeIndex(df.tail(1)['Timestamp']).year==1900:
        df = df.iloc[:-1]

    if time_as_dt:
        # Convert time stamp into time differences in seconds. This means we have to remove the first data
        # point.
        dt = np.diff(df.iloc[:,0]).astype(int)/1e9
        df = df.iloc[1:,:]
        df['Timestamp'] = df['Timestamp'].apply(pd.to_numeric,errors='coerce')
        df['Timestamp'] = dt
    return df

