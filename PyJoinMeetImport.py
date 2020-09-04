#!/usr/bin/env python3
import os
import sys
import zipfile
import time
import configparser

print("PyJoinMeet v0.0.1, A Simple Python Script to Join a Google Meet")
print("Copyright (C) Antony Jr.")
print("")


if len(sys.argv) < 2:
    print("Usage: ./PyJoinMeetImport.py [Export Filename]")
    sys.exit()


export_file = sys.argv[1]

data_dir = '{}/PyJoinMeet'.format(os.path.expanduser('~'))

if not os.path.exists(data_dir):
    try:
        os.mkdir(data_dir)
    except:
        print("ERROR: cannot create data dir")
        sys.exit(-1)

cur = os.getcwd()
os.chdir(data_dir)
zf = zipfile.ZipFile('{}/{}'.format(cur,export_file))
zf.extractall()
zf.close()
os.chdir(cur)

sys.exit(0)
