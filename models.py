import pytz
import util

from google.appengine.ext import db
from google.appengine.api import memcache

class SavingsAccount(db.Model):
  parent_user = db.UserProperty()
  child_first_name = db.StringProperty()
  child_image = db.BlobProperty()
  open_datetime = db.DateTimeProperty(auto_now_add=True)
  currency = db.StringProperty()
  interest_rate = db.FloatProperty()
  interest_compound_frequency = db.StringProperty(
      choices=set(['weekly', 'monthly']))
  opening_balance = db.IntegerProperty()
  allowance_amount = db.IntegerProperty()
  allowance_frequency = db.StringProperty(
      choices=set(['weekly', 'monthly']))
  # will determine the day of the allowance dispersal
  allowance_start_date = db.DateProperty()
  timezone_name = db.StringProperty()

  def getOpeningBalanceForPrinting(self):
    return util.formatMoney(self.opening_balance)

  def getFormattedOpenDate(self):
    return util.formatShortDate(self.getOpenDatetime())

  def getOpenDate(self):
    return self.getOpenDatetime().date()

  def getOpenDatetime(self):
    open_datetime = self.open_datetime.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(self.timezone_name))
    return open_datetime

  def getAllowanceStartDate(self):
    return util.formatShortDate(self.allowance_start_date)

  # TODO(jgessner): move the memcache stuff to AccountList.
  def getBalance(self):
    cache_key = '%s_balance' % self.key()
    balance = memcache.get(cache_key)
    if balance is not None:
      return balance

    balance = self.calculateBalance()
    memcache.set(cache_key, balance, 30)
    return balance

  def calculateBalance(self, max_time=None):
    transactions = AccountTransaction.getTransactionsForAccount(self, max_time)
    balance = self.opening_balance
    for transaction in transactions:
      if transaction.transaction_type == 'withdrawal':
        balance -= transaction.amount
      else:
        balance += transaction.amount
    return balance

  def getBalanceForPrinting(self):
    return '%.2f' % (self.getBalance() / 1000000.0)

  # TODO(jgessner): move the ForPrinting methods somewhere else.
  def getAllowanceAmountForPrinting(self):
    return util.formatMoney(self.allowance_amount)


class AccountTransaction(db.Model):
  savings_account = db.ReferenceProperty(SavingsAccount)
  transaction_type = db.StringProperty(choices=set(['interest',
                                                    'allowance',
                                                    'deposit',
                                                    'withdrawal']))
  transaction_time = db.DateTimeProperty(auto_now_add=True)
  transaction_local_date = db.DateProperty()
  amount = db.IntegerProperty()
  memo = db.StringProperty()

  def getAmountForPrinting(self):
    return util.formatMoney(self.amount)

  def FormattedDate(self):
    return getYMDInCentralTime(self.transaction_time)

  @staticmethod
  def getTransactionsForAccount(account, max_time=None):
    transactions_query = AccountTransaction.all()
    transactions_query.filter('savings_account', account)
    if max_time:
      transactions_query.filter('transaction_time <=', max_time)
    transactions_query.order('-transaction_time')
    transactions = transactions_query.fetch(100)
    return transactions

  @staticmethod
  def hasAllowanceForDate(account, transaction_date):
    return AccountTransaction.hasTransactionOnDateOfType(account, transaction_date, 'allowance') 

  @staticmethod
  def hasInterestForDate(account, transaction_date):
    return AccountTransaction.hasTransactionOnDateOfType(account, transaction_date, 'interest') 

  @staticmethod
  def hasTransactionOnDateOfType(account, transaction_date, transaction_type):
    allowance_query = AccountTransaction.all()
    allowance_query.filter('savings_account', account)
    allowance_query.filter('transaction_local_date', transaction_date)
    allowance_query.filter('transaction_type', transaction_type)
    allowance_results = allowance_query.fetch(1)
    return len(allowance_results) > 0

class SaverParent(db.Model):
  email = db.StringProperty()
  name = db.StringProperty()
  nickname = db.StringProperty()
  date_added = db.DateTimeProperty(auto_now_add=True)
  # Invitation Key will be cleared out when an invitation is accepted.
  invitation_key = db.StringProperty()
