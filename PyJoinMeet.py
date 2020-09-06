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
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException


def getMinValue(now):
    return (now.hour * 60) + now.minute

print("PyJoinMeet v0.0.1, A Simple Python Script to Join a Google Meet")
print("Copyright (C) Antony Jr.")
print("")


if len(sys.argv) < 3:
    print("Usage: ./PyJoinMeet.py [Google Username] [Google Meet URL]")
    sys.exit()



actual_user = sys.argv[1]
google_user = hashlib.md5(bytes(sys.argv[1], 'utf-8')).digest().hex()
google_meet_url = sys.argv[2]

data_dir = '{}/PyJoinMeet'.format(os.path.expanduser('~'))
chrome_driver_path = '{}/chromedriver'.format(data_dir)

if not os.path.exists(data_dir):
    try:
        os.mkdir(data_dir)
    except:
        print("ERROR: cannot create data dir")
        sys.exit(-1)

if not os.path.exists('{}/{}'.format(data_dir, google_user)):
    print("ERROR: Please Import User Data for {}".format(actual_user))
    sys.exit()

if not os.path.exists('{}/{}/pyjoinmeet.ini'.format(data_dir, google_user)):
    print("ERROR: Invalid Import for {}, cannot find pyjoinmeet.ini".format(actual_user))
    sys.exit()


# Check gecko driver
if not os.path.exists(chrome_driver_path):
    print("Please download and put the chromedriver at {}.".format(data_dir))
    sys.exit(-1)

options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--user-data-dir={}/{}".format(data_dir, google_user))
options.add_argument("start-maximized")
options.add_argument("--disable-infobars")
options.add_argument("--disable-extensions")
options.add_argument("--disable-gpu")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches" , ["enable-automation","load-extension", "test-type"])
options.add_experimental_option("prefs", { \
    "profile.default_content_setting_values.media_stream_mic": 1,
    "profile.default_content_setting_values.media_stream_camera": 1,
    "profile.default_content_setting_values.notifications": 1
})

config = configparser.ConfigParser()
config.read('{}/{}/pyjoinmeet.ini'.format(data_dir, google_user))

days = {
    "monday" : 7,
    "mon" : 7,
    "tuesday" : 1,
    "tue": 1,
    "wednesday" : 2,
    "wed" : 2,
    "thu" : 3,
    "thursday": 3,
    "friday" : 4,
    "fri" : 4,
    "saturday": 5,
    "sat": 5,
}

timezone = None
for i in pytz.all_timezones:
    if config['DEFAULT']['timezone'].lower() in i.lower():
        timezone = pytz.timezone(i)
        break;

if timezone is None:
    print("ERROR: Invalid Timezone")
    driver.close()
    sys.exit(0)

start_day = config['DEFAULT']['startday'].lower()
end_day = config['DEFAULT']['endday'].lower()

start_time = config['DEFAULT']['starttime'].lower()
end_time = config['DEFAULT']['endtime'].lower()

while True:
    if start_day not in days or end_day not in days:
        print("WARNING: Invalid day range, abort.")
        break;

    now = datetime.now(timezone)
    if now.day >= days[start_day] and now.day <= days[end_day]:
        print("INFO: Wating for the right time to join class")

        start = start_time.split(':')
        end = end_time.split(':')

        # Convert everything to minutes.
        startMinValue = (int(start[0]) * 60) + int(start[1]) 
        endMinValue = (int(end[0]) * 60) + int(end[1])
        
        now = datetime.now(timezone) # Get the required current timee
        nowMinValue = getMinValue(now)

        if startMinValue <= nowMinValue and endMinValue >= nowMinValue:
            # Join the class now
            print("INFO: Joining Meet {} as {}.".format(google_meet_url, actual_user))

            # Start the driver
            driver = webdriver.Chrome(options=options, executable_path=chrome_driver_path)
            
            joined = False
            driver.get(google_meet_url)
            time.sleep(10)

            try:
                driver.find_element_by_xpath("//span[contains(text(), 'Join now' )]").click()
                joined = True
            except NoSuchElementException:
                try:
                    driver.find_element_by_xpath("//span[contains(text(), 'Ask to join')]").click()
                    joined = True
                except NoSuchElementException:
                    print("WARNING: Cannot JOIN")
                    joined = False

            while True:
                if not joined:
                    print("WARNING: Cannot JOIN")

                now = datetime.now(timezone) # Get the required current time.
                nowMinValue = getMinValue(now)
                if nowMinValue > endMinValue:
                    break
                time.sleep(30)

            # End Class
            if joined:
                print("Now Hour: {}, Now Minute: {}".format(now.hour, now.minute))
                print("INFO: Leaving Meet {} as {}.".format(google_meet_url, actual_user))
                driver.close()

            else:
                print("FATAL: Did not attend session because could not join")

        time.sleep(5);
    else:
        time.sleep(30);
    
sys.exit()
