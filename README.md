# PyJoinMeet

A Simple Python Script to join a google meet.

# Instructions

```
 $ ./PyJoinMeetUserData.py youraccount@gmail.com yourexportfilename
```

You need to execute the ```PyJoinMeetUserData.py``` in your local computer.
**Make sure you have Chromium or Chrome installed.**

Also download the correct chrome webdriver and put it at ```/home/username/PyJoinMeet/```.

In execution of ```PyJoinMeetUserData.py```, you will get a browser. Using the browser 
login into your google account which you use to join the meet.

Once finished. Press enter at the terminal and please don't close the Web browser yourself.

Now execute this command with the given export file at your server or remote computer or your
computer itself.

```
 $ ./PyJoinMeetImport.py yourexportfilename
```

Now Finally Run.

```
 $ ./PyJoinMeet.py [GOOGLE Meet URL] [Your Username Only]
```

# Using Telegram Bot

Set your **API Token** in the environmental variable ```PYJOINMEET_BOT_TOKEN```. Then you have to add your Telegram userid to 
the ```PyJoinMeetBot.json``` file as a json array. Only userid present in the file will be allowed access.

Now copy the PyJoinMeetBot.json to ```~/PyJoinMeet/PyJoinMeetBot.json```.
