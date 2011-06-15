import cgi
import imghdr
import logging
import os
import time

from datetime import datetime
from datetime import date
from datetime import timedelta
from datetime import tzinfo
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db

kTemplatesDir = os.path.join(os.path.dirname(__file__), 'templates')

# TODO(jgessner): move these utility functions into their own little class.
def getTemplatePath(template):
  return os.path.join(kTemplatesDir, template)

def getYMDInCentralTime(datetime_value):
  return datetime.fromtimestamp(time.mktime(datetime_value.utctimetuple()),
                                Central_tzinfo()).strftime('%Y-%m-%d')

def formatMoney(amount_in_micros):
  return "%.2f" % (amount_in_micros / 1000000.00)

def formatShortDate(date_value):
  return date_value.strftime('%Y-%m-%d')

def parseShortDate(date_string):
  return datetime.strptime(date_string, '%Y-%m-%d').date()


class Index(webapp.RequestHandler):
  def get(self):
    if users.get_current_user():
      url =  users.create_logout_url('/')
      url_linktext =  'Logout'
    else:
      # send users to the accounts list after logging in
      url = users.create_login_url('/accounts')
      url_linktext = 'Login'
    template_values = {
      'current_user': users.get_current_user(),
      'url': url,
      'url_linktext': url_linktext,
    }
    self.response.out.write(template.render(getTemplatePath('index.html'),
                                            template_values))

class HowTo(webapp.RequestHandler):
  def get(self):
    if users.get_current_user():
      url =  users.create_logout_url('/')
      url_linktext =  'Logout'
    else:
      # send users to the accounts list after logging in
      url = users.create_login_url('/howto')
      url_linktext = 'Login'
    template_values = {
      'current_user': users.get_current_user(),
      'url': url,
      'url_linktext': url_linktext,
    }
    self.response.out.write(template.render(getTemplatePath('howto.html'),
                                            template_values))


class SavingsAccount(db.Model):
  parent_user = db.UserProperty()
  child_first_name = db.StringProperty()
  child_image = db.BlobProperty()
  open_date = db.DateProperty(auto_now_add=True)
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

  def getImgSrc(self):
    if self.child_image:
      return '<img src="/pic?account=%s" width=200 height=200 />' % self.key()
    else:
      return ""

  def getOpeningBalanceForPrinting(self):
    return formatMoney(self.opening_balance)

  def getOpenDate(self):
    return formatShortDate(self.open_date)

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
      if transaction.transaction_type != 'allowance_to_cash':
        if transaction.transaction_type == 'withdrawal':
          balance -= transaction.amount
        else:
          balance += transaction.amount
    return balance

  def getBalanceForPrinting(self):
    return '%.2f' % (self.getBalance() / 1000000.0)

  # TODO(jgessner): move the ForPrinting methods somewhere else.
  def getAllowanceAmountForPrinting(self):
    return formatMoney(self.allowance_amount)

  def hasPendingTransactions(self, transaction_date=None, find_any_status=False):
    return PendingAccountTransaction.hasPendingTransactions(self, transaction_date, find_any_status)


class AccountTransaction(db.Model):
  savings_account = db.ReferenceProperty(SavingsAccount)
  transaction_type = db.StringProperty(choices=set(['interest',
                                                    'allowance_to_savings',
                                                    'allowance_to_cash',
                                                    'withdrawal']))
  transaction_time = db.DateTimeProperty(auto_now_add=True)
  amount = db.IntegerProperty()

  def getAmountForPrinting(self):
    return formatMoney(self.amount)

  @staticmethod
  def getTransactionsForAccount(account, max_time=None):
    transactions_query = AccountTransaction.all()
    transactions_query.filter('savings_account', account)
    if max_time:
      transactions_query.filter('transaction_time <=', max_time)
    transactions_query.order('-transaction_time')
    transactions = transactions_query.fetch(100)
    return transactions


class PendingAccountTransaction(db.Model):
  savings_account = db.ReferenceProperty(SavingsAccount)
  transaction_date = db.DateProperty()
  amount = db.IntegerProperty()
  processed = db.BooleanProperty()

  def getAmountForPrinting(self):
    return "%.2f" % (self.amount / 1000000.00)

  @staticmethod
  def getPendingTransactionsForAccount(account):
    pending_transactions_query = PendingAccountTransaction.all()
    pending_transactions_query.filter('savings_account', account)
    pending_transactions_query.filter('processed', False)
    pending_transactions_query.order('-transaction_date')
    pending_transactions = pending_transactions_query.fetch(100)
    return pending_transactions

  @staticmethod
  def hasPendingTransactions(account, transaction_date=None, find_any_status=False):
    pending_query = PendingAccountTransaction.all()
    pending_query.filter('savings_account', account)
    if not find_any_status:
      pending_query.filter('processed', False)
    if transaction_date:
      pending_query.filter('transaction_date', transaction_date)
    pending_results = pending_query.fetch(1)
    return len(pending_results) > 0


class SavingsAccountList(webapp.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    accounts_query = SavingsAccount.all()
    accounts_query.order('child_first_name')
    accounts_query.filter('parent_user', users.get_current_user())
    accounts = accounts_query.fetch(100)
    transactions = dict()
    for account in accounts:
      transactions[account.key()] = AccountTransaction.getTransactionsForAccount(account)

    accounts_left = []
    accounts_right = []
    account_num = 0
    for account in accounts:
      account_num += 1
      if account_num % 2 != 0:
        accounts_left.append(account)
      else:
        accounts_right.append(account)

    template_values = {
      'current_user': users.get_current_user(),
      'accounts_left': accounts_left,
      'accounts_right': accounts_right,
      'transactions': transactions,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('account_list.html'), template_values))


class SavingsAccountNew(webapp.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    template_values = {
      'today': getYMDInCentralTime(datetime.now()),
      'current_user': users.get_current_user(),
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }
    self.response.out.write(template.render(
        getTemplatePath('account_new.html'), template_values))

  def post(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account = SavingsAccount()
    account.parent_user = users.get_current_user()
    account.child_first_name = self.request.get('child_first_name')
    # TODO(jgessner): make this a best fit instead of a blind resize
    if self.request.get("child_image"):
      account.child_image = images.resize(self.request.get("child_image"), 200, 200)
    account.currency = self.request.get('currency')
    account.interest_rate = float(self.request.get('interest_rate'))
    account.interest_compound_frequency = self.request.get('interest_compound_frequency')
    # TODO(jgessner): make a constant for the micros value
    account.opening_balance = int(float(self.request.get('opening_balance')) * 1000000)
    account.allowance_amount = int(float(self.request.get('allowance_amount')) * 1000000)
    account.allowance_frequency = self.request.get('allowance_frequency')
    account.allowance_start_date = parseShortDate(self.request.get('allowance_start_date'))

    account.put()

    self.redirect('/accounts')


class SavingsAccountEdit(webapp.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    key = self.request.get('account')
    account = db.get(key)
    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('account_edit.html'), template_values))

  def post(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    key = self.request.get('account')
    account = db.get(key)
    account.parent_user = users.get_current_user()
    account.child_first_name = self.request.get('child_first_name')
    # TODO(jgessner): make this a best fit instead of a blind resize
    if self.request.get("child_image"):
      account.child_image = images.resize(self.request.get("child_image"), 200, 200)
    account.currency = self.request.get('currency')
    account.interest_rate = float(self.request.get('interest_rate'))
    account.interest_compound_frequency = self.request.get('interest_compound_frequency')
    account.open_date =  parseShortDate(self.request.get('open_date'))
    account.opening_balance = int(float(self.request.get('opening_balance')) * 1000000)
    account.allowance_amount = int(float(self.request.get('allowance_amount')) * 1000000)
    account.allowance_frequency = self.request.get('allowance_frequency')
    account.allowance_start_date = parseShortDate(self.request.get('allowance_start_date'))
    account.put()

    account.child_first_name = self.request.get('child_first_name')
    account.put()

    self.redirect('/accounts')


class TransactionNew(webapp.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    key = self.request.get('account')
    account = db.get(key)
    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('transaction_new.html'), template_values))

  def post(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account_key = self.request.get('account')
    account = db.get(account_key)

    transaction = AccountTransaction()
    transaction.savings_account = account
    transaction.transaction_type = self.request.get('transaction_type')
    transaction.amount = int(float(self.request.get('amount')) * 1000000)
    transaction.put()

    self.redirect('/accounts')


class TransactionList(webapp.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account = SavingsAccount.get(self.request.get('account'))
    transactions_query = AccountTransaction.all()
    transactions_query.filter('savings_account', account)
    transactions_query.order('transaction_time')
    transactions = transactions_query.fetch(100)

    balance = account.opening_balance
    processed_transactions = []
    processed_transactions.append({
      'date': account.open_date,
      'type': 'Opening Balance',
      'amount': '%.2f' % (account.opening_balance/ 1000000.0),
      'balance': '%.2f' % (balance / 1000000.0),
    })
    for transaction in transactions:
      if transaction.transaction_type in ['allowance_to_savings', 'interest']:
        balance += transaction.amount
      elif transaction.transaction_type == 'withdrawal':
        balance -= transaction.amount

      processed_transactions.append({
        'date': getYMDInCentralTime(transaction.transaction_time),
        'type': transaction.transaction_type,
        'amount': '%.2f' % (transaction.amount / 1000000.0),
        'balance': '%.2f' % (balance / 1000000.0),
      })
    processed_transactions.reverse()

    pending_transactions = PendingAccountTransaction.getPendingTransactionsForAccount(account)

    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'transactions': processed_transactions,
      'pending_transactions': pending_transactions,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('transaction_list.html'), template_values))


class Pic(webapp.RequestHandler):
  def detect_mime_type(self, image):
    if image[1:4] == 'PNG': return 'image/png'
    if image[0:3] == 'GIF': return 'image/gif'
    if image[6:10] == 'JFIF': return 'image/jpeg'
    return None

  def get(self):
    account = SavingsAccount.get(self.request.get('account'))
    if account.child_image:
      filetype = self.detect_mime_type(account.child_image)
      self.response.headers['Content-Type'] = filetype
      self.response.out.write(account.child_image)
    else:
      self.response.out.write('no image found')


class ProcessAllowanceSchedules(webapp.RequestHandler):
  def get(self):
    accounts_query = SavingsAccount.all()
    accounts = accounts_query.fetch(100)
    for account in accounts:
      today = datetime.now(Central_tzinfo()).date()
      should_schedule_allowance_payment = False
      if account.allowance_frequency == 'weekly':
        days_between = today - account.allowance_start_date
        if days_between.days >= 0 and days_between.days % 7 == 0:
          should_schedule_allowance_payment = True
      else:
        if today.day == allowance_start_date.day:
          should_schedule_allowance_payment = True

      logging.info('Should i schedule the %s allowance of %s starting %s for %s? %s' % (account.allowance_frequency, account.getAllowanceAmountForPrinting(), account.allowance_start_date, account.child_first_name, should_schedule_allowance_payment))
      if should_schedule_allowance_payment:
        scheduled = False
        pending_found = PendingAccountTransaction.hasPendingTransactions(account, transaction_date=today, find_any_status=True)
        if not pending_found:
          pending_transaction = PendingAccountTransaction()
          pending_transaction.savings_account = account
          pending_transaction.amount = account.allowance_amount
          pending_transaction.transaction_date = today
          pending_transaction.processed = False
          pending_transaction.put()
          scheduled = True
        logging.info("Scheduled? %s" % scheduled)


class AllocateAllowance(webapp.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account = SavingsAccount.get(self.request.get('account'))
    pending_query = PendingAccountTransaction.all()
    pending_query.filter('savings_account', account)
    pending_query.filter('transaction_date', parseShortDate(self.request.get('date')))
    pending_transactions = pending_query.fetch(1)
    # TODO(jgessner): make a flash message if there is an error
    if len(pending_transactions) == 0:
      self.redirect('/accounts')
    pending_transaction = pending_transactions[0]

    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'pending_transaction': pending_transaction,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('allocate_allowance.html'), template_values))


  def post(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account = SavingsAccount.get(self.request.get('account'))
    pending_query = PendingAccountTransaction.all()
    pending_query.filter('savings_account', account)
    pending_query.filter('transaction_date', parseShortDate(self.request.get('date')))
    pending_transactions = pending_query.fetch(1)
    # TODO(jgessner): make a flash message if there is an error
    if len(pending_transactions) == 0:
      self.redirect('/accounts')
    pending_transaction = pending_transactions[0]

    # make sure the allocation amounts add up
    savings_amount = int(float(self.request.get('save_amount')) * 1000000)
    cash_amount = int(float(self.request.get('pocket_amount')) * 1000000)
    submitted_total = savings_amount + cash_amount
    if submitted_total == pending_transaction.amount:
      transaction = AccountTransaction()
      transaction.savings_account = account
      transaction.transaction_type = 'allowance_to_savings'
      transaction.amount = savings_amount
      transaction.put()

      transaction = AccountTransaction()
      transaction.savings_account = account
      transaction.transaction_type = 'allowance_to_cash'
      transaction.amount = cash_amount
      transaction.put()

      pending_transaction.processed = True
      pending_transaction.put()

    self.redirect('/accounts')


class PayInterest(webapp.RequestHandler):
  def get(self):
    self.response.out.write("processing interest payments!<br />")
    accounts_query = SavingsAccount.all()
    accounts = accounts_query.fetch(100)
    for account in accounts:
      today = datetime.now(Central_tzinfo()).date()
      yesterday = today + timedelta(days=-1)
      yesterday_transaction_time = datetime(
          yesterday.year,
          yesterday.month,
          yesterday.day,
          23, 59, 59, 999999, Central_tzinfo())
      should_schedule_interest_payment = False
      if account.interest_compound_frequency == 'weekly':
        days_between = yesterday - account.open_date
        if days_between.days > 0 and days_between.days % 7 == 0:
          should_schedule_interest_payment = True
      else:
        if yesterday > account.open_date and yesterday.day == account.open_date.day:
          should_schedule_interest_payment = True

      self.response.out.write('Should i pay interest %s for %s? %s<br />' % (account.getAllowanceAmountForPrinting(), account.child_first_name, should_schedule_interest_payment))
      if should_schedule_interest_payment:
        scheduled = False
        # TODO(jgessner): move this into AccountTransaction
        interest_query = AccountTransaction.all()
        interest_query.filter('savings_account', account)
        interest_query.filter('transaction_time', yesterday_transaction_time)
        interest_query.filter('transaction_type', 'interest')
        interest_results = interest_query.fetch(1)
        interest_found = False
        for p in interest_results:
          interest_found = True
        if not interest_found:
          bad_interest_amount = int(account.calculateBalance() * (account.interest_rate / 100))
          interest_amount = int(account.calculateBalance(max_time=yesterday_transaction_time) * (account.interest_rate / 100))
          interest_transaction = AccountTransaction()
          interest_transaction.savings_account = account
          interest_transaction.transaction_type = 'interest'
          interest_transaction.amount = interest_amount
          interest_transaction.transaction_time = yesterday_transaction_time
          interest_transaction.put()
          scheduled = True
        self.response.out.write("Scheduled? %s<br />" % scheduled)


# stolen from http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html#datetime
# this is utter madness.
class Central_tzinfo(tzinfo):
  """Implementation of the US Central timezone."""
  def utcoffset(self, dt):
    return timedelta(hours=-6) + self.dst(dt)

  def _FirstSunday(self, dt):
    """First Sunday on or after dt."""
    return dt + timedelta(days=(6-dt.weekday()))

  def dst(self, dt):
    # 2 am on the second Sunday in March
    dst_start = self._FirstSunday(datetime(dt.year, 3, 8, 2))
    # 1 am on the first Sunday in November
    dst_end = self._FirstSunday(datetime(dt.year, 11, 1, 1))

    if dst_start <= dt.replace(tzinfo=None) < dst_end:
      return timedelta(hours=1)
    else:
      return timedelta(hours=0)
  def tzname(self, dt):
    if self.dst(dt) == timedelta(hours=0):
      return "CST"
    else:
      return "CDT"

application = webapp.WSGIApplication(
                                     [('/', Index),
                                      ('/howto', HowTo),
                                      ('/accounts', SavingsAccountList),
                                      ('/account_new', SavingsAccountNew),
                                      ('/account_edit', SavingsAccountEdit),
                                      ('/transaction_list', TransactionList),
                                      ('/transaction_new', TransactionNew),
                                      ('/pic', Pic),
                                      ('/allocate_allowance', AllocateAllowance),
                                      ('/process_allowance_schedules', ProcessAllowanceSchedules),
                                      ('/pay_interest', PayInterest),
                                     ], debug=True)

def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
