#!/usr/bin/env python3
# A Telegram Bot to do joins automatically from a Telegram message away
import os
import json
import pytz
import hashlib
import stat
import sys
import requests
import tempfile
import zipfile
import configparser
import threading
import urllib.parse
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException


store = {} # Stores all the requested schedule
store_lock = threading.Lock()


def getMinValue(now):
    return (now.hour * 60) + now.minute

def send_message(token, chatid, message):
    msg_enc = urllib.parse.quote(message)
    response = requests.get("https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}"
                             .format(token, chatid, msg_enc))
    if response.status_code != 200:
        print("WARNING: sendMessage returned {}".format(response.status_code))
        return False
    return True
 

class BotInstance(object):
    def __init__(self, google_meet_url, actual_user, start_time, end_time, start_day, end_day, zone, token, chatid):
        global store
        global store_lock
        store_lock.acquire()

        self.stop_requested = False
        google_meet_url = google_meet_url.lower()
        if google_meet_url in store.keys():
            store[google_meet_url].stop()
        store[google_meet_url] = self
        
        store_lock.release()

        self.token = token
        self.chatid = chatid
        self.google_meet_url = google_meet_url
        
        arguments = (google_meet_url, actual_user.lower(), start_time.lower(), end_time.lower(), start_day.lower(), end_day.lower(), zone)
        self.thread = threading.Thread(target = self._run, args=arguments)
        self.thread.start()
        self.lock = threading.Lock()
      
    def stop(self):
        self.lock.acquire()
        self.stop_requested = True
        self.lock.release()
        return True

    def remove(self):
        global store
        global store_lock
        store_lock.acquire()
        if self.google_meet_url in store:
            del store[self.google_meet_url]
        store_lock.release()

    def _run(self, google_meet_url, actual_user, start_time, end_time, start_day, end_day,zone):
        google_user = hashlib.md5(bytes(actual_user, 'utf-8')).digest().hex()
        data_dir = '{}/PyJoinMeet'.format(os.path.expanduser('~'))
        chrome_driver_path = '{}/chromedriver'.format(data_dir)
        if not os.path.exists('{}/{}'.format(data_dir, google_user)):
            send_message(self.token, self.chatid, "[!] Could not add, No User Data found!")
            print("ERROR: Please Import User Data for {}".format(actual_user))
            self.remove()
            return

        # Check gecko driver
        if not os.path.exists(chrome_driver_path):
            send_message(self.token, self.chatid, "[!] Could not add, Please install PyJoinMeet correctly!")
            print("Please download and put the chromedriver at {}.".format(data_dir))
            self.remove()
            return

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

        days = {
            "monday" : 0,
            "mon" : 0,
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
            if zone.lower() == i.lower():
                timezone = pytz.timezone(i)

        if timezone is None:
            print("ERROR: Invalid Timezone")
            send_message(self.token, self.chatid, "[!] Could not add, Invalid Timezone!")
            self.remove()
            return 

        if start_day not in days or end_day not in days:
                print("WARNING: Invalid day range, abort.")
                send_message(self.token, self.chatid, "[!] Could not add, Invalid Day")
                self.remove()
                return;

        if days[start_day] > days[end_day]:
                print("WARNING: Invalid day range, abort.")
                send_message(self.token, self.chatid, "[!] Could not add, Invalid Day Range. Must From < To")
                self.remove()
                return;

        start = start_time.split(':')
        end = end_time.split(':')
        if len(start) != 2 or len(end) != 2:
            send_message(self.token, self.chatid, "[!] Could not add, Invalid Time given. Must be HH:MM")
            self.remove()
            return;

        if (int(start[0]) * 60) + int(start[1]) > (int(end[0]) * 60) + int(end[1]):
            send_message(self.token, self.chatid, "[!] Could not add, Invalid Time Range. Must  From < To")
            self.remove()
            return;

        send_message(self.token, self.chatid, "Added {} as {} scheduled to meet at from {} to {}, {}-{}"
                                               .format(google_meet_url, actual_user, start_time, end_time, start_day, end_day))
        while True:
            self.lock.acquire()
            if self.stop_requested:
                self.lock.release()
                break;
            self.lock.release()

            now = datetime.now(timezone)
            if now.weekday() >= days[start_day] and now.weekday() <= days[end_day]:
                print("INFO: {}:: Wating for the right time to join class".format(google_meet_url))

                start = start_time.split(':')
                end = end_time.split(':')

                # Convert everything to minutes.
                startMinValue = (int(start[0]) * 60) + int(start[1]) 
                endMinValue = (int(end[0]) * 60) + int(end[1])
        
                now = datetime.now(timezone) # Get the required current timee
                nowMinValue = getMinValue(now)

                if startMinValue <= nowMinValue and endMinValue >= nowMinValue:
                    send_message(self.token, self.chatid, "Trying to join {} as {}".format(google_meet_url, actual_user))
      
                    # Join the class now
                    print("INFO: Joining Meet {} as {}.".format(google_meet_url, actual_user))

                    # Start the driver
                    driver = webdriver.Chrome(options=options, executable_path=chrome_driver_path)
                    joined = False
                    driver.get(google_meet_url)
                    sleep(10)

                
                    proceed = False
                    tries = 0
                    while not proceed:
                        try:
                            try:
                                driver.find_element_by_xpath("//span[contains(text(), 'Join now' )]").click()
                                joined = True
                                proceed = True
                            except NoSuchElementException:
                                try:
                                    driver.find_element_by_xpath("//span[contains(text(), 'Ask to join')]").click()
                                    joined = True
                                    proceed = True
                                except NoSuchElementException:
                                    print("WARNING: Cannot JOIN")
                                    joined = False
                                    proceed = True
                        except:
                            if tries > 5:
                                proceed = True
                            else:
                                tries += 1
                                sleep(5)

                    if not joined:
                        send_message(self.token, self.chatid, "[!] Cannot join {} as {}, Server error!".format(google_meet_url, actual_user))
                    else:
                        send_message(self.token, self.chatid, "Successfully joined {} as {}.".format(google_meet_url, actual_user))
 
                    while True:
                        if not joined:
                            print("WARNING: Cannot JOIN")

                        now = datetime.now(timezone) # Get the required current time.
                        nowMinValue = getMinValue(now)
                        if nowMinValue > endMinValue:
                            break

                        self.lock.acquire()
                        if self.stop_requested:
                            self.lock.release()
                            break;
                        self.lock.release()
                        sleep(30)

                    # End Class
                    if joined:
                        print("INFO: Leaving Meet {} as {}.".format(google_meet_url, actual_user))
                        driver.close()
                    else:
                        print("FATAL: Did not attend session because could not join")
                        send_message(self.token, self.chatid, "Did not attend {} as {}, Fatal error at server".format(google_meet_url, actual_user))
                sleep(10);   
            else:
                sleep(30);

        send_message(self.token, self.chatid, "Left {} successfully!".format(google_meet_url))
        if self.stop_requested:
            send_message(self.token, self.chatid, "Removed {} from server successfully!".format(google_meet_url))
        
def main(zone):
    if not os.path.exists("{}/PyJoinMeet/PyJoinMeetBot.json".format(os.path.expanduser('~'))):
        print("FATAL: Please copy your PyJoinMeetBot.json to ~/PyJoinMeet. abort!")
        sys.exit(-1)
    
    allowed_userids = None
    try:
        with open("{}/PyJoinMeet/PyJoinMeetBot.json".format(os.path.expanduser('~')), "r") as fp:
            allowed_userids = json.load(fp)
    except:
        print("FATAL: Unable to parse PyJoinMeetBot.json. abort!")
        sys.exit(-1)
    
    token = os.getenv("PYJOINMEET_BOT_TOKEN")
    if token is None:
        print("FATAL: No bot token, abort!")
        sys.exit(-1)

    tapiurl = "https://api.telegram.org/bot{}".format(token)
    offset = 0 # Offset of the last seen message
    global store
    global store_lock

    while True:
        response = requests.get("{}/getUpdates?offset={}".format(tapiurl, offset))
        if response.status_code != 200:
            print("WARNING: getUpdates returned {}".format(response.status_code))
            sleep(5)
            continue
        try:
            json_data = json.loads(response.content)
        except:
            print("WARNING: cannot parse json")
            sleep(5)
            continue

        if json_data['ok'] != True:
            print("WARNING: API Request failed")
            sleep(5)
            continue


        for i in json_data['result']:
            offset = int(i['update_id']) + 1

            # Check if the user is allowed
            userid = str(i['message']['from']['id'])
            chatid = str(i['message']['chat']['id'])
            if userid not in allowed_userids.keys():
                message = "You are not an authorized user. You have been shot!"
                send_message(token, chatid, message)
                continue

            try:
                actual_user = allowed_userids[userid]["google_user"]
            except:
                send_message(token, chatid, "Could not add because google_user is not mentioned in server config.")
                continue
            
            # Now execute the requested command
            text = i['message']['text']
            args = text.split(',')

            if args[0].lower() == 'stop':
                if len(args) != 2:
                    send_message(token, chatid, "Please send stop along with a google meet url")
                    continue
                google_meet_url = args[1].strip()
                store_lock.acquire()
                if google_meet_url not in store:
                    send_message(token, chatid, "No meet was scheduled, maybe stopped earlier?")
                    store_lock.release()
                    continue

                store[google_meet_url].stop() # Stop the Bot Instance
                del store[google_meet_url]
                send_message(token, chatid, "Okay, I will stop it ASAP. Please wait for confirmation though!")
                store_lock.release()
                continue

            if len(args) != 3:
                send_message(token, chatid, "Invalid format")
                send_message(token, chatid, "The format is: <google meet url>, <start time>-<end time>, <start day>-<end day>")
                send_message(token, chatid, "The time should be in 24 hour format")
                send_message(token, chatid, "Valid days are: Mon, Tue, Wed, Thu, Fri, Sat")
                continue
            
            google_meet_url = args[0].strip()
            time = args[1].strip()
            day = args[2].strip()

            times = time.split('-')
            start_time = times[0]
            end_time = times[1]
            
            days = day.split('-')
            start_day = days[0]
            end_day = days[1]

            store_lock.acquire()
            if google_meet_url in store:
                send_message(token, chatid, "The meet url already has a schedule.")
                send_message(token, chatid, "You can send: stop <google meet url> to stop the meeting and remove it from schedule.")
                store_lock.release()
                continue
            store_lock.release()

            BotInstance(google_meet_url, actual_user, start_time, end_time, start_day, end_day, zone, token, chatid)

        # Sleep some time to avoid over usage of the CPU time
        sleep(5)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: ./PyJoinMeetBot.py [Time Zone]")
        print("Example: ./PyJoinMeetBot.py Asia/Kolkata")
        sys.exit()

    zone = sys.argv[1]
    print("Using Zone:: {}".format(zone))
    main(zone)
