def getMinValue(now):
    return (now.hour * 60) + now.minute

class Now(object):
    def __init__(self, hour=0, minute=0):
        self.hour = hour
        self.minute = minute
        self.days = 0

    def increament(self):
        self.minute += 1
        if self.minute >= 60:
            self.hour += 1
            self.minute -= 60
            if self.hour >= 24:
                self.hour = 0
                self.minute = 0
                self.days += 1


now = Now()
start = ['09', '00']
end = ['14', '50']

days = 4

while True:
    endMinValue = (int(end[0]) * 60) + int(end[1])
    startMinValue = (int(start[0]) * 60) + int(start[1])
    nowMinValue = getMinValue(now)
    if startMinValue <= nowMinValue and endMinValue >= nowMinValue:
            print("Enter google classroom at {}:{}.".format(now.hour, now.minute))
            while True:
                    now.increament()
                    nowMinValue = getMinValue(now)
                    if nowMinValue > endMinValue:
                            break;
            print("Leaving Class at {}:{}.".format(now.hour, now.minute))
    now.increament()
    if now.days >= days:
        break
