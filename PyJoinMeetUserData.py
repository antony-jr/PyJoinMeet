#!/usr/bin/env python3
import os
import pytz
import hashlib
import stat
import sys
import requests
import tempfile
import zipfile
import time
import configparser
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))

'''
    zipf = zipfile.ZipFile('Python.zip', 'w', zipfile.ZIP_DEFLATED)
    zipdir('tmp/', zipf)
    zipf.close()
'''

print("PyJoinMeet v0.0.1, A Simple Python Script to Join a Google Meet")
print("Copyright (C) Antony Jr.")
print("")


if len(sys.argv) < 3:
    print("Usage: ./PyJoinMeetUserData.py [Google Username] [Export Filename]")
    sys.exit()


google_user = hashlib.md5(bytes(sys.argv[1], 'utf-8')).digest().hex()
export = sys.argv[2]

data_dir = '{}/PyJoinMeet'.format(os.path.expanduser('~'))
chrome_driver_path = '{}/chromedriver'.format(data_dir)

if not os.path.exists(data_dir):
    try:
        os.mkdir(data_dir)
    except:
        print("ERROR: cannot create data dir")
        sys.exit(-1)


# Check gecko driver
if not os.path.exists(chrome_driver_path):
    print("Please download and put the chromedriver at {}.".format(data_dir))
    sys.exit(-1)

print("Starting configuration... ")
for i in pytz.all_timezones:
    print(i)
timezone = input("Please enter your timezone: ")

while timezone not in pytz.all_timezones:
    for i in pytz.all_timezones:
        print(i)
    timezone = input("Please enter a valid timezone: ")

start_time = input("Please enter start time(In 24 Hour format): ")
end_time = input("Please enter end time(In 24 Hour format): ")
start_day = input("Enter start Day(Mon/Monday): ")
end_day = input("Enter end Day(Friday/Fri): ")

print("Please go to your google account url and login.")
print("Please don't close the webbrowser yourself.")
print("Press Enter Key to finish the setup.")

options = webdriver.ChromeOptions()
options.add_argument("--user-data-dir={}/{}".format(data_dir, google_user))
options.add_argument("start-maximized")
options.add_argument("--disable-infobars")
options.add_argument("--disable-extensions")
options.add_argument("--disable-gpu")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches" , ["enable-automation","load-extension", "test-type"])
driver = webdriver.Chrome(options=options, executable_path=chrome_driver_path)

input("Please press Enter Key to finish the login process.")

config = configparser.ConfigParser()
config['DEFAULT']['timezone'] = timezone
config['DEFAULT']['starttime'] = start_time
config['DEFAULT']['endtime'] = end_time
config['DEFAULT']['startday'] = start_day
config['DEFAULT']['endday'] = end_day

with open('{}/{}/pyjoinmeet.ini'.format(data_dir, google_user), 'w') as fp:
    config.write(fp)

driver.close()

cur = os.getcwd()
os.chdir(data_dir)
zipf = zipfile.ZipFile('{}/{}.zip'.format(cur,export), 'w', zipfile.ZIP_DEFLATED)
zipdir('{}'.format(google_user), zipf)
zipf.close()
os.chdir(cur)

sys.exit(0)
