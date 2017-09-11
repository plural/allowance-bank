import cgi
import imghdr
import logging
import os
import pytz
import time
import util
import webapp2

from Crypto.Hash import SHA256
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from google.appengine.api import images
from google.appengine.api import mail
from google.appengine.api import taskqueue
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from models import AccountTransaction
from models import SavingsAccount

kTemplatesDir = os.path.join(os.path.dirname(__file__), 'templates')

# TODO(jgessner): move these utility functions into their own little class.
def getTemplatePath(template):
  return os.path.join(kTemplatesDir, template)

class Index(webapp2.RequestHandler):
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

class HowTo(webapp2.RequestHandler):
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


class SavingsAccountList(webapp2.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    accounts_query = SavingsAccount.query()
    accounts_query.order(SavingsAccount.child_first_name)
    accounts_query.filter(SavingsAccount.parent_user == users.get_current_user())
    accounts = accounts_query.fetch(100)

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
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('account_list.html'), template_values))


class SavingsAccountNew(webapp2.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    timezone_names = pytz.all_timezones # common_timezones
    print '\nThere are %d common timezones.\n' % len(timezone_names)
    timezone_names.sort()
    print '\nThere are %d common timezones.\n' % len(timezone_names)
    template_values = {
      'current_user': users.get_current_user(),
      'timezone_names': timezone_names,
      'today': date.today().strftime('%Y-%m-%d'),
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
    account.child_email = self.request.get('child_email')
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
    account.allowance_start_date = util.parseShortDate(self.request.get('allowance_start_date'))
    account.timezone_name = self.request.get('account_timezone')

    account.put()

    self.redirect('/accounts')


class SavingsAccountEdit(webapp2.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    key = ndb.Key(urlsafe=self.request.get('account'))
    account = key.get() 

    timezone_names = pytz.common_timezones
    timezone_names.sort()

    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'timezone_names': timezone_names,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('account_edit.html'), template_values))

  def post(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    key = ndb.Key(urlsafe=self.request.get('account'))
    account = key.get()
    account.parent_user = users.get_current_user()
    account.child_first_name = self.request.get('child_first_name')
    account.child_email = self.request.get('child_email')
    # TODO(jgessner): make this a best fit instead of a blind resize
    if self.request.get("child_image"):
      account.child_image = images.resize(self.request.get("child_image"), 200, 200)
    account.currency = self.request.get('currency')
    account.interest_rate = float(self.request.get('interest_rate'))
    account.interest_compound_frequency = self.request.get('interest_compound_frequency')
    account.opening_balance = int(float(self.request.get('opening_balance')) * 1000000)
    account.allowance_amount = int(float(self.request.get('allowance_amount')) * 1000000)
    account.allowance_frequency = self.request.get('allowance_frequency')
    account.allowance_start_date = util.parseShortDate(self.request.get('allowance_start_date'))
    account.put()

    # TODO(jgessner): huh?
    account.child_first_name = self.request.get('child_first_name')
    account.put()

    self.redirect('/accounts')

class TransactionNew(webapp2.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    key = ndb.Key(urlsafe=self.request.get('account'))
    account = key.get()
    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('transaction_new.html'), template_values))
  
  @ndb.transactional
  def saveNewTransaction(self, account, transaction_type, transaction_amount, memo):
    transaction = AccountTransaction(parent=account.key)
    # TODO(jgessner): remove the extra savings_account field.
    transaction.savings_account = account.key
    transaction.transaction_type = transaction_type
    transaction.amount = int(float(transaction_amount) * 1000000)
    transaction.transaction_local_date = util.getTodayForTimezone(account.timezone_name)
    transaction.memo = memo
    transaction.put()
    return transaction.key

  def post(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account_key = ndb.Key(urlsafe=self.request.get('account'))
    account = account_key.get()

    transaction_key = self.saveNewTransaction(account, self.request.get('transaction_type'), self.request.get('amount'), self.request.get('memo'))

    task = taskqueue.add(
        url='/send_transaction_email',
        params={
            'account': account.key.urlsafe(),
            'transaction': transaction_key.urlsafe(),
            })

    self.redirect('/accounts')


class TransactionList(webapp2.RequestHandler):
  def get(self):
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))

    account_key = ndb.Key(urlsafe=self.request.get('account'))
    account = account_key.get()
    transactions_query = AccountTransaction.query(ancestor=account_key)
    transactions_query = transactions_query.order(AccountTransaction.transaction_time)
    transactions = transactions_query.fetch(1000)

    balance = account.opening_balance
    # Start off with the opening balance as a transaction.
    processed_transactions = [{
      'date': account.getFormattedOpenDate(),
      'type': 'Opening Balance',
      'memo': '',
      'amount': '%.2f' % (account.opening_balance / 1000000.0),
      'balance': '%.2f' % (balance / 1000000.0),
    }]
    for transaction in transactions:
      if transaction.transaction_type == 'withdrawal':
        balance -= transaction.amount
      else:
        balance += transaction.amount

      memo = transaction.memo
      if memo == None:
          memo = ''
      processed_transactions.append({
        'date': util.formatShortDate(transaction.transaction_local_date),
        'type': transaction.transaction_type,
        'memo': memo,
        'amount': '%.2f' % (transaction.amount / 1000000.0),
        'balance': '%.2f' % (balance / 1000000.0),
      })
    processed_transactions.reverse()

    template_values = {
      'current_user': users.get_current_user(),
      'account': account,
      'transactions': processed_transactions,
      'url': users.create_logout_url('/'),
      'url_linktext': 'Logout',
    }

    self.response.out.write(template.render(
        getTemplatePath('transaction_list.html'), template_values))


class Pic(webapp2.RequestHandler):
  def detect_mime_type(self, image):
    if image[1:4] == 'PNG': return 'image/png'
    if image[0:3] == 'GIF': return 'image/gif'
    if image[6:10] == 'JFIF': return 'image/jpeg'
    return None

  def get(self):
    account_key = ndb.Key(urlsafe=self.request.get('account'))
    account = account_key.get()
    if account.child_image:
      filetype = self.detect_mime_type(account.child_image)
      self.response.headers['Content-Type'] = filetype
      self.response.out.write(account.child_image)
    else:
      self.response.out.write('no image found')


class ProcessAllowanceSchedules(webapp2.RequestHandler):
  def get(self):
    accounts_query = SavingsAccount.query()
    accounts = accounts_query.fetch(100)
    for account in accounts:
      today = util.getTodayForTimezone(account.timezone_name)
      should_schedule_allowance_payment = False
      if account.allowance_frequency == 'weekly':
        days_between = today - account.allowance_start_date
        if days_between.days >= 0 and days_between.days % 7 == 0:
          should_schedule_allowance_payment = True
        else:
          logging.info("Not the right day to schedule weekly allowance for %s", account.child_first_name)
      else:
        # Monthly
        # TODO(jgessner): Deal with a Feb 29 start date.
        if today.day == allowance_start_date.day:
          should_schedule_allowance_payment = True
        else:
          logging.info("Not the right day to schedule monthly allowance for %s", account.child_first_name)

      logging.info('Should i schedule the %s allowance of %s starting %s for %s? %s' % (account.allowance_frequency, account.getAllowanceAmountForPrinting(), account.allowance_start_date, account.child_first_name, should_schedule_allowance_payment))
      if should_schedule_allowance_payment:
        if not AccountTransaction.hasAllowanceForDate(account, transaction_date=today):
          transaction = AccountTransaction(parent=account.key)
          transaction.savings_account = account.key
          transaction.transaction_type = 'allowance'
          transaction.transaction_local_date = today
          transaction.amount = account.allowance_amount
          transaction.put()
          task = taskqueue.add(
              url='/send_transaction_email',
              params={
                  'account': account.key.urlsafe(),
                  'transaction': transaction.key.urlsafe(),
                  })


# TODO(jgessner): Make most of this an instance method on SavingsAccount
class PayInterest(webapp2.RequestHandler):
  def get(self):
    accounts_query = SavingsAccount.query()
    accounts = accounts_query.fetch(100)
    for account in accounts:
      today = util.getTodayForTimezone(account.timezone_name)
      yesterday = today + timedelta(days=-1)
      # The transaction time must be in UTC, but that really means it can't have a tzinfo.
      yesterday_transaction_time = datetime(
          yesterday.year,
          yesterday.month,
          yesterday.day,
          23, 59, 59, 999999, pytz.timezone(account.timezone_name)).astimezone(pytz.UTC).replace(tzinfo=None)
      logging.info('Transaction time is %s', yesterday_transaction_time)
      should_schedule_interest_payment = False
      if account.interest_compound_frequency == 'weekly':
        days_between = yesterday - account.getOpenDate()
        if days_between.days > 0 and days_between.days % 7 == 0:
          should_schedule_interest_payment = True
        else:
          logging.info('Not the right day to schedule weekly interest payment for %s', account.child_first_name)
      else:
        if yesterday > account.open_datetime and yesterday.day == account.open_datetime.day:
          should_schedule_interest_payment = True
        else:
          logging.info('Not the right day to schedule monthly interest payment for %s', account.child_first_name)

      if should_schedule_interest_payment:
        logging.info('It is the right day to pay interest for %s', account.child_first_name)
        if not AccountTransaction.hasInterestForDate(account, transaction_date=yesterday):
          interest_amount = int(account.calculateBalance(max_time=yesterday_transaction_time) * (account.interest_rate / 100))
          interest_transaction = AccountTransaction(parent=account.key)
          interest_transaction.savings_account = account.key
          interest_transaction.transaction_type = 'interest'
          interest_transaction.amount = interest_amount
          interest_transaction.transaction_time = yesterday_transaction_time
          interest_transaction.transaction_local_date = yesterday
          interest_transaction.put()
          task = taskqueue.add(
              url='/send_transaction_email',
              params={
                  'account': account.key.urlsafe(),
                  'transaction': interest_transaction.key.urlsafe(),
                  })
          logging.info('Interest payment %0.2f processed for %s', (interest_amount / 1000000.0), account.child_first_name)
        else:
          logging.info('Interest payment already processed for %s', account.child_first_name)


class SetParentsHandler(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain' 
    if not users.get_current_user():
      self.redirect(users.create_login_url(self.request.uri))
    t_query = AccountTransaction.query()

    for t in t_query:
      self.response.out.write('Transaction: %s\n' % t.key)
      if not t.key.parent():
        self.response.out.write('No parent for this transaction, making a copy\n')
        t2 = AccountTransaction(parent=t.savings_account)
        t2.savings_account = t.savings_account
        t2.transaction_type = t.transaction_type
        t2.transaction_time = t.transaction_time
        t2.transaction_local_date = t.transaction_local_date
        t2.amount = t.amount
        t2.memo = t.memo
        t2.put()
        self.response.out.write('  New transaction key: %s\n' % t2.key)
        self.response.out.write('  Deleting %s\n' % t.key)
        t.key.delete()


class SendTransactionEmailHandler(webapp2.RequestHandler):
  def post(self):
    account = ndb.Key(urlsafe=self.request.get('account')).get()
    balance = account.calculateBalance() 

    transaction = ndb.Key(urlsafe=self.request.get('transaction')).get()
    logging.info('Details from triggering transaction is %s', transaction)

    mail.send_mail(sender='transaction@allowance-bank-hrd.appspotmail.com',
                   to="%s <%s>" % (account.child_first_name, account.child_email),
                   cc="gessners@multiply.org",
                   subject="Something happened in your Allowance Bank",
                   body="""Oh hello, %s!

A new transaction was just recorded for your account.
Transaction Type: %s
Transaction Amount: $%s
Memo: %s

New Balance: $%s
""" % (
    account.child_first_name,
    transaction.transaction_type,
    util.formatMoney(transaction.amount),
    transaction.memo,
    util.formatMoney(balance)))


application = webapp2.WSGIApplication(
                                     [('/', Index),
                                      ('/howto', HowTo),
                                      ('/accounts', SavingsAccountList),
                                      ('/account_new', SavingsAccountNew),
                                      ('/account_edit', SavingsAccountEdit),
                                      ('/transaction_list', TransactionList),
                                      ('/transaction_new', TransactionNew),
                                      ('/pic', Pic),
                                      ('/process_allowance_schedules', ProcessAllowanceSchedules),
                                      ('/pay_interest', PayInterest),
                                      ('/send_transaction_email', SendTransactionEmailHandler),
                                      # ('/set_parents', SetParentsHandler),
                                     ], debug=True)
