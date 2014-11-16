import pytz

from datetime import datetime

def getNowForTimezone(timezone_name):
  return datetime.now().replace(tzinfo=pytz.utc).astimezone(pytz.timezone(timezone_name))

def getTodayForTimezone(timezone_name):
  return getNowForTimezone(timezone_name).date()

def formatMoney(amount_in_micros):
  return "%.2f" % (amount_in_micros / 1000000.00)

def formatShortDate(date_value):
  return date_value.strftime('%Y-%m-%d')

def parseShortDate(date_string):
  return datetime.strptime(date_string, '%Y-%m-%d').date()
