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


nick_store = {} # Stores all nickname of the key in store
nick_store_lock = threading.Lock()

store = {} # Stores all the requested schedule
store_lock = threading.Lock()


def getMinValue(now):
    return (now.hour * 60) + now.minute

def send_message(token, chatid, message):
    msg_enc = urllib.parse.quote(message)
    try:
       response = requests.get("https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}"
                               .format(token, chatid, msg_enc))
    except:
        print("WARNING: sendMessage raised an exception, the message is not sent.")
        return False

    if response.status_code != 200:
        print("WARNING: sendMessage returned {}".format(response.status_code))
        return False
    return True
 

class BotInstance(object):
    def __init__(self, google_meet_url, actual_user, start_time, end_time, start_day, end_day, token, chatid, nick):
        global store
        global store_lock
        store_lock.acquire()

        self.actual_user = actual_user

        self.avoid_join = None
        self.leave_requested = False
        self.resume_requested = False
        self.stop_requested = False
        self.nick = nick

        if actual_user not in store:
            store[actual_user] = {}

        google_meet_url = google_meet_url.lower()
        if google_meet_url in store[actual_user]:
            store[actual_user][google_meet_url].stop()
        store[actual_user][google_meet_url] = self
        
        store_lock.release()

        self.token = token
        self.chatid = chatid
        self.google_meet_url = google_meet_url
   
        self.timing = "{}-{}".format(start_time, end_time)
        self.ondays = "{}-{}".format(start_day, end_day)
   
        self.lock = threading.Lock()
        arguments = (google_meet_url, actual_user.lower(), start_time.lower(), end_time.lower(), start_day.lower(), end_day.lower())
        self.thread = threading.Thread(target = self._run, args=arguments)
        self.thread.start()
        
    def getschedule(self):
        r = "Meet from {} on {} for {}({}).\n\n"
        self.lock.acquire()
        r = r.format(self.timing, self.ondays, self.nick, self.google_meet_url)
        self.lock.release()
        return r
    
    def setnick(self, new_nick):
        self.lock.acquire()
        self.nick = new_nick
        self.lock.release()

    def resume(self):
        self.lock.acquire()
        if self.avoid_join is not None:
            self.resume_requested = True
        self.lock.release()
        return True

    def leave(self):
        self.lock.acquire()
        self.leave_requested = True
        self.lock.release()
        return True

    def stop(self):
        self.lock.acquire()
        self.stop_requested = True
        self.lock.release()
        return True

    def remove(self):
        global store
        global store_lock
        store_lock.acquire()
        if self.actual_user in store:
            if self.google_meet_url in store[self.actual_user]:
                del store[self.actual_user][self.google_meet_url]
        store_lock.release()

    def _run(self, google_meet_url, actual_user, start_time, end_time, start_day, end_day):
        zone = None
        google_user = hashlib.md5(bytes(actual_user, 'utf-8')).digest().hex()
        data_dir = '{}/PyJoinMeet'.format(os.path.expanduser('~'))
        chrome_driver_path = '{}/chromedriver'.format(data_dir)
        if not os.path.exists('{}/{}'.format(data_dir, google_user)):
            send_message(self.token, self.chatid, "[!] Could not add, No User Data found!")
            print("ERROR: Please Import User Data for {}".format(actual_user))
            self.remove()
            return

        # Get Timezone for the User Data
        config = configparser.ConfigParser()
        try:
            config.read("{}/{}/pyjoinmeet.ini".format(data_dir, google_user))
            zone = config['DEFAULT']['timezone']
        except:
            send_message(self.token, self.chatid, "[!] Could not add, Cannot get Timzone for user!")
            print("ERROR: Cannot get timezone for {}".format(actual_user))
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
            "sunday" : 6,
            "sun" : 6
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

        try:
            start0 = int(start[0])
            start1 = int(start[1])
            end0 = int(end[0])
            end1 = int(end[1])
        except:
            send_message(self.token, self.chatid, "[!] Could not add, Invalid time value. Must be a Integer")
            self.remove()
            return;



        if (int(start[0]) * 60) + int(start[1]) > (int(end[0]) * 60) + int(end[1]):
            send_message(self.token, self.chatid, "[!] Could not add, Invalid Time Range. Must  From < To")
            self.remove()
            return;

        try:
            res = requests.get(google_meet_url);

            if res.status_code >= 400:
                send_message(self.token, self.chatid, "[!] Could not add, Cannot react {}".format(google_meet_url))
                self.remove()
                return;
        except:
            send_message(self.token, self.chatid, "[!] Could not add, Cannot reach {}".format(google_meet_url))
            self.remove()
            return;

        nick = None
        self.lock.acquire()
        nick = self.nick
        self.lock.release()
        
        if nick is not None:
            send_message(self.token, self.chatid, "Added {}({}) scheduled to meet from {} to {}, {}-{} by {}"
                                               .format(nick, google_meet_url, start_time, end_time, start_day, end_day,actual_user))
        else:
            send_message(self.token, self.chatid, "Added {} scheduled to meet from {} to {}, {}-{} by {}"
                                               .format(google_meet_url, start_time, end_time, start_day, end_day,actual_user))
       
        while True:
            now = datetime.now(timezone)
            
            self.lock.acquire()
            nick = self.nick
            
            if self.stop_requested:
                self.lock.release()
                break;

            if self.resume_requested:
                self.resume_requested = False
                self.avoid_join = None
                self.lock.release()
                continue

            if self.avoid_join is not None and self.avoid_join == now.day:
                self.lock.release()
                sleep(10)
                continue
            elif self.avoid_join is not None and self.avoid_join != now.day:
                self.avoid_join = None
            self.lock.release()

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
                    if nick is not None:
                        send_message(self.token, self.chatid, "Trying to join {}({}) as {}".format(nick, google_meet_url, actual_user))
                    else:
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
                        if nick is not None:
                            send_message(self.token, self.chatid, "[!] Cannot join {}({}), Server error!".format(nick, google_meet_url))
                        else:
                            send_message(self.token, self.chatid, "[!] Cannot join {} as {}, Server error!".format(google_meet_url, actual_user))
                    else:
                        if self.nick is not None:
                            send_message(self.token, self.chatid, "Successfully joined {}({}) as {}."
                                                                  .format(nick, google_meet_url, actual_user))
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

                        if self.leave_requested:
                            self.leave_requested = False
                            self.avoid_join = now.day
                            self.lock.release()
                            break;
                        self.lock.release()
                        sleep(30)

                    # End Class
                    if joined:
                        print("INFO: Leaving Meet {} as {}.".format(google_meet_url, actual_user))
                        driver.close()
                        driver.quit()
                        
                        if nick is not None:
                            send_message(self.token, self.chatid, "Left {}({}) as {}".format(nick, google_meet_url, actual_user))
                        else:
                            send_message(self.token, self.chatid, "Left {} as {}".format(google_meet_url, actual_user))
                    else:
                        print("FATAL: Did not attend session because could not join")
                        if nick is not None:
                            send_message(self.token, self.chatid, "Did not attend {}({}), Fatal error at server".format(nick, google_meet_url))
                        else:
                            send_message(self.token, self.chatid, "Did not attend {} as {}, Fatal error at server".format(google_meet_url, actual_user))
                sleep(10);   
            else:
                sleep(30);

        if self.stop_requested:
            if nick is not None:
                send_message(self.token, self.chatid, "{}({}) Instace Completely stopped from server successfully!".format(nick, google_meet_url))
            else:
                send_message(self.token, self.chatid, "{} Instace Completely stopped from server successfully!".format(google_meet_url))
        
def main():
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
    global nick_store
    global nick_store_lock
    
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
            try:
                userid = str(i['message']['from']['id'])
                chatid = str(i['message']['chat']['id'])
            except:
                continue

            if userid not in allowed_userids.keys():
                text = i['message']['text']
                text_split = text.split(' ')
                args = []
                for i in text_split:
                    if len(i) == 0:
                        continue
                    args.append(i)

                msg = None
                if args[0].lower() == '/start':
                    msg = "Welcome to PyJoinMeet, A Python Script to Join Google Meet Automatically.\n"
                    msg += "PyJoinMeet is made by Antony Jr.(https://antonyjr.in).\n\n"
                    msg += "You are not authorized with this server.\n"
                    msg += "You're Telegram UserID: {}"
                    msg = msg.format(userid)
                else:
                    msg = "You are not an authorized user. You have been shot!"
                send_message(token, chatid, msg)
                continue

            try:
                actual_user = allowed_userids[userid]["google_user"]
            except:
                send_message(token, chatid, "Could not add because google_user is not mentioned in server config.")
                continue
            
            # Now execute the requested command
            text = i['message']['text']
            text_split = text.split(' ')
            args = []
            for i in text_split:
                if len(i) == 0:
                    continue
                args.append(i)

            if args[0].lower() == '/start':
                msg = "Welcome to PyJoinMeet, A Python Script to Join Google Meet Automatically.\n"
                msg += "PyJoinMeet is made by Antony Jr.(https://antonyjr.in).\n\n"
                msg += "You are currently authorized with this server.\n"
                msg += "Type /help to get more info on how to use this."
                send_message(token, chatid, msg)
                continue
            if args[0].lower() == 'my':
                if len(args) != 2:
                    send_message(token, chatid, "Available my commands: my schedule, my account")
                    continue
                
                subcom = args[1].strip()
                if subcom.lower() == "schedule":
                    nick_store_lock.acquire()
                    store_lock.acquire()
                    if actual_user not in nick_store or actual_user not in store:
                        send_message(token, chatid, "You have no schedule at all.")
                        nick_store_lock.release()
                        store_lock.release()
                    else:
                        r = []
                        for i in nick_store[actual_user]:
                            if nick_store[actual_user][i] not in store[actual_user]:
                                continue
                            r.append((store[actual_user][nick_store[actual_user][i]]).getschedule())
                        
                        msg = "".join(r)
                        if len(msg) == 0:
                            msg = "You have no schedule at all!"

                        send_message(token, chatid, msg)
                        nick_store_lock.release()
                        store_lock.release()
                elif subcom.lower() == "account":
                    send_message(token, chatid, "Your account google user: {}".format(actual_user))
                else:
                    send_message(token, chatid, "Available my commands: my schedule, my account")
                continue
            elif args[0].lower() == 'stop':
                if len(args) != 2:
                    send_message(token, chatid, "Please send stop along with a google meet url or nickname")
                    continue
                nick_avail = False
                google_meet_url = None
                google_meet_url_or_nick = args[1].strip()
                store_lock.acquire()
                nick_store_lock.acquire()
                if actual_user not in store:
                    store[actual_user] = {}
                    send_message(token, chatid, "No meet was scheduled, maybe stopped earlier?")
                    store_lock.release()
                    nick_store_lock.release()
                    continue

                if actual_user in nick_store:
                    if google_meet_url_or_nick in nick_store[actual_user]:
                        google_meet_url = nick_store[actual_user][google_meet_url_or_nick]
                        nick_avail = True
                    else:
                        google_meet_url = google_meet_url_or_nick
                else:
                    google_meet_url = google_meet_url_or_nick
                    
                # Find the nick name if only google meet url is given
                if not nick_avail:
                    if actual_user in nick_store:
                        for i in nick_store[actual_user]:
                            if nick_store[actual_user][i] == google_meet_url:
                                google_meet_url_or_nick = i
                                nick_avail = True
                                break
                                

                if google_meet_url not in store[actual_user]:
                    send_message(token, chatid, "No such meet url or nickname!")
                    store_lock.release()
                    nick_store_lock.release()
                    continue

                store[actual_user][google_meet_url].stop() # Stop the Bot Instance
                del store[actual_user][google_meet_url]
                if nick_avail:
                    del nick_store[actual_user][google_meet_url_or_nick]
                    send_message(token, chatid, "Removed {}({}) from schedule.".format(google_meet_url_or_nick, google_meet_url))
                else:
                    send_message(token, chatid, "Removed {} from schedule.".format(google_meet_url))
                send_message(token, chatid, "If the bot is already joined the meet then wait for confirmation of leaving.")
                store_lock.release()
                nick_store_lock.release()
                continue
            elif args[0].lower() == 'leave':
                if len(args) != 2:
                    send_message(token, chatid, "Please send leave along with a google meet url or nickname")
                    continue
                nick_avail = False
                google_meet_url = None
                google_meet_url_or_nick = args[1].strip()
                store_lock.acquire()
                nick_store_lock.acquire()
                if actual_user not in store:
                    store[actual_user] = {}
                    send_message(token, chatid, "No meet was scheduled, maybe stopped earlier?")
                    store_lock.release()
                    nick_store_lock.release()
                    continue

                if actual_user in nick_store:
                    if google_meet_url_or_nick in nick_store[actual_user]:
                        google_meet_url = nick_store[actual_user][google_meet_url_or_nick]
                        nick_avail = True
                    else:
                        google_meet_url = google_meet_url_or_nick
                else:
                    google_meet_url = google_meet_url_or_nick

                if google_meet_url not in store[actual_user]:
                    send_message(token, chatid, "No such meet url or nickname!")
                    store_lock.release()
                    nick_store_lock.release()
                    continue

                store[actual_user][google_meet_url].leave() # Stop the Bot Instance
                if nick_avail:
                    send_message(token, chatid, "Okay will be leaving {}({}) only for today.".format(google_meet_url_or_nick, google_meet_url))
                else:
                    send_message(token, chatid, "Okay will be leaving {} only for today.".format(google_meet_url))
                send_message(token, chatid, "If the bot is already joined the meet then wait for confirmation of leaving.")
                store_lock.release()
                nick_store_lock.release()
                continue
            elif args[0].lower() == 'resume':
                if len(args) != 2:
                    send_message(token, chatid, "Please send resume along with a google meet url or nickname")
                    continue
                changed = False
                google_meet_url = None
                google_meet_url_or_nick = args[1].strip()
                store_lock.acquire()
                nick_store_lock.acquire()
                if actual_user not in store:
                    store[actual_user] = {}
                    send_message(token, chatid, "No meet was scheduled, maybe stopped earlier?")
                    store_lock.release()
                    nick_store_lock.release()
                    continue

                if actual_user in nick_store:
                    if google_meet_url_or_nick in nick_store[actual_user]:
                        google_meet_url = nick_store[actual_user][google_meet_url_or_nick]
                        nick_avail = True
                    else:
                        google_meet_url = google_meet_url_or_nick
                else:
                    google_meet_url = google_meet_url_or_nick

                if google_meet_url not in store[actual_user]:
                    send_message(token, chatid, "No such meet url or nickname!")
                    store_lock.release()
                    nick_store_lock.release()
                    continue

                store[actual_user][google_meet_url].resume() # Resume Bot Instance
                if nick_avail:
                    send_message(token, chatid, "Okay will be resuming {}({}) if it is left.".format(google_meet_url_or_nick, google_meet_url))
                else:
                    send_message(token, chatid, "Okay will be resuming {} only if it is left.".format(google_meet_url))
                store_lock.release()
                nick_store_lock.release()
                continue
            elif args[0].lower() == 'setnick':
                if len(args) != 3:
                    send_message(token, chatid, "Please send setnick along with a google meet url and nickname")
                    continue
                google_meet_url = args[1].strip()
                new_nick = args[2].strip()
                store_lock.acquire()
                nick_store_lock.acquire()
                
                if actual_user not in nick_store or actual_user not in store:
                    nick_store[actual_user] = {}
                    store[actual_user] = {}
                    send_message(token, chatid, "No meet was scheduled, maybe stopped earlier?")
                    store_lock.release()
                    nick_store_lock.release()
                    continue
                
                if google_meet_url not in store[actual_user]:
                    send_message(token, chatid, "No meet was scheduled, maybe stopped earlier?")
                    store_lock.release()
                    nick_store_lock.release()
                    continue
                
                for i in nick_store[actual_user]:
                    if nick_store[actual_user][i] == google_meet_url:
                        del nick_store[actual_user][i]
                        nick_store[actual_user][new_nick] = google_meet_url
                        store[actual_user][google_meet_url].setnick(new_nick)
                        changed = True
                        break
                
                if not changed:
                    send_message(token, chatid, "No such nickname for your account!")
                else:
                    send_message(token, chatid, "{} is now aliased to {}.".format(google_meet_url, new_nick))
                    
                store_lock.release()
                nick_store_lock.release()
                continue
            else:
                if len(args) != 3 and len(args) != 4:
                    send_message(token, chatid, "Invalid format")
                    send_message(token, chatid, 
                                 "The format is: <google meet url> <start time>-<end time> <start day>-<end day> <nickname is optional>")
                    send_message(token, chatid, "The time should be in 24 hour format")
                    send_message(token, chatid, "Valid days are: Mon, Tue, Wed, Thu, Fri, Sat")
                    send_message(token, chatid, "Nickname is not compulsion")
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

            nick = None
            if len(args) == 4:
                nick = args[3]

            store_lock.acquire()
            if actual_user not in store:
                store[actual_user] = {}
            
            if google_meet_url in store[actual_user]:
                send_message(token, chatid, "The meet url already has a schedule.")
                send_message(token, chatid, "You can send: stop <google meet url or nickname> to stop the meeting and remove it from schedule.")
                store_lock.release()
                continue
            store_lock.release()

            if nick is not None:
                nick_store_lock.acquire()
                if actual_user not in nick_store:
                    nick_store[actual_user] = {}
                    nick_store[actual_user][nick] = google_meet_url
                else:
                    if nick in nick_store[actual_user]:
                        send_message(token, chatid, "The nickname is aliased to {} already.".format(nick_store[actual_user][nick]))
                        send_message(token, chatid, "You can send: stop <google meet url or nickname> to stop the meeting and remove it from schedule.")
                        nick_store_lock.release()
                        continue
                    else:
                        nick_store[actual_user][nick] = google_meet_url
                nick_store_lock.release()

            BotInstance(google_meet_url, actual_user, start_time, end_time, start_day, end_day, token, chatid, nick)

        # Sleep some time to avoid over usage of the CPU time
        sleep(5)

if __name__ == '__main__':
    print("PyJoinMeet v0.0.1, A Simple Python Script to Join a Google Meet")
    print("Copyright (C) Antony Jr.")
    print("")

    main()
