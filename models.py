import pytz
import util

from google.appengine.ext import ndb
from google.appengine.api import memcache

class SavingsAccount(ndb.Model):
  parent_user = ndb.UserProperty()
  child_first_name = ndb.StringProperty()
  child_image = ndb.BlobProperty()
  open_datetime = ndb.DateTimeProperty(auto_now_add=True)
  currency = ndb.StringProperty()
  interest_rate = ndb.FloatProperty()
  interest_compound_frequency = ndb.StringProperty(
      choices=set(['weekly', 'monthly']))
  opening_balance = ndb.IntegerProperty()
  allowance_amount = ndb.IntegerProperty()
  allowance_frequency = ndb.StringProperty(
      choices=set(['weekly', 'monthly']))
  # will determine the day of the allowance dispersal
  allowance_start_date = ndb.DateProperty()
  timezone_name = ndb.StringProperty()

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
    cache_key = '%s_balance' % self.key
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


class AccountTransaction(ndb.Model):
  savings_account = ndb.KeyProperty(kind=SavingsAccount)
  transaction_type = ndb.StringProperty(choices=set(
      ['interest', 'allowance', 'deposit', 'withdrawal']))
  transaction_time = ndb.DateTimeProperty(auto_now_add=True)
  transaction_local_date = ndb.DateProperty()
  amount = ndb.IntegerProperty()
  memo = ndb.StringProperty()

  def getAmountForPrinting(self):
    return util.formatMoney(self.amount)

  def FormattedDate(self):
    return getYMDInCentralTime(self.transaction_time)

  @staticmethod
  def getTransactionsForAccount(account, max_time=None):
    transactions_query = AccountTransaction.query()
    transactions_query = transactions_query.filter(AccountTransaction.savings_account == account.key)
    if max_time:
      transactions_query = transactions_query.filter(AccountTransaction.transaction_time <= max_time)
    transactions_query = transactions_query.order(AccountTransaction.transaction_time)
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
    query = AccountTransaction.query()
    query = query.filter(AccountTransaction.savings_account == account.key)
    query = query.filter(AccountTransaction.transaction_local_date == transaction_date)
    query = query.filter(AccountTransaction.transaction_type == transaction_type)
    return len(query.fetch(1)) > 0

class SaverParent(ndb.Model):
  email = ndb.StringProperty()
  name = ndb.StringProperty()
  nickname = ndb.StringProperty()
  date_added = ndb.DateTimeProperty(auto_now_add=True)
  # Invitation Key will be cleared out when an invitation is accepted.
  invitation_key = ndb.StringProperty()
