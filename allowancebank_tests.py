import os
import time
import unittest

from allowancebank import AccountTransaction
from allowancebank import Central_tzinfo
from allowancebank import PendingAccountTransaction
from allowancebank import SavingsAccount
from datetime import date
from datetime import datetime
from datetime import timedelta
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
from google.appengine.api import mail_stub
from google.appengine.api import urlfetch_stub
from google.appengine.api import user_service_stub
from google.appengine.api.users import User
from webtest import TestApp

class AppEngineTestCase(unittest.TestCase):
  APP_ID = u'allowance-bank'
  AUTH_DOMAIN = 'gmail.com'
  LOGGED_IN_USER = ''
  LOGGED_IN_USER_ID = ''

  user = User(email = 'test@gmail.com')
  account = SavingsAccount(parent_user = user)

  def setUp(self):
    os.environ['SERVER_NAME'] = 'localhost'
    os.environ['SERVER_PORT'] = '8080'
    os.environ['AUTH_DOMAIN'] = self.AUTH_DOMAIN
    os.environ['USER_EMAIL'] = self.LOGGED_IN_USER
    os.environ['USER_ID'] = self.LOGGED_IN_USER_ID
    # Ensure we're in UTC.
    os.environ['TZ'] = 'UTC'
    time.tzset()

    # Start with a fresh api proxy.
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
    # Use a fresh stub datastore.
    stub = datastore_file_stub.DatastoreFileStub(self.APP_ID, '/dev/null', '/dev/null')
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', stub)
    # Use a fresh stub UserService.
    apiproxy_stub_map.apiproxy.RegisterStub('user', user_service_stub.UserServiceStub())
    # Use a fresh urlfetch stub.
    apiproxy_stub_map.apiproxy.RegisterStub('urlfetch', urlfetch_stub.URLFetchServiceStub())
    # Use a fresh mail stub.
    apiproxy_stub_map.apiproxy.RegisterStub('mail', mail_stub.MailServiceStub())

def createPendingTransaction(account, amount, date, processed):
  pending_transaction_yesterday = PendingAccountTransaction()
  pending_transaction_yesterday.savings_account = account
  pending_transaction_yesterday.amount = amount
  pending_transaction_yesterday.transaction_date = date
  pending_transaction_yesterday.processed = processed
  pending_transaction_yesterday.put()


class TestSavingsAccount(AppEngineTestCase):
  def test_creation(self):
    self.account.put()
    fetched_account = SavingsAccount.all().filter('parent_user', self.user).fetch(1)[0]
    self.assertEquals(fetched_account.parent_user, self.user)

  def test_getOpenDate(self):
    self.account.open_date = date(2010, 12, 23)
    self.assertEquals('2010-12-23', self.account.getOpenDate())

  def test_printableAmounts(self):
    self.account.opening_balance = 4540000
    self.account.allowance_amount = 5000000
    self.assertEquals('4.54', self.account.getOpeningBalanceForPrinting())
    self.assertEquals('5.00', self.account.getAllowanceAmountForPrinting())

  def test_getImgSrc(self):
    # need the account to have a key
    self.account.put()

    self.assertFalse(self.account.getImgSrc())

    self.account.child_image = "abcdefg"
    img_tag = ('<img src="/pic?account=%s" width=200 height=200 />'
           % self.account.key())
    self.assertEqual(img_tag, self.account.getImgSrc())


  # TODO(jgessner): this should really be a test against PendingTransaction with a mock version in the SavingsAccount test or just code for PendingAccountTransactions
  def test_hasPendingTransactions(self):
    self.account.put()
    # no pending transactions in the datastore
    self.assertEquals(0, len(PendingAccountTransaction.all().fetch(100)))
    self.assertFalse(self.account.hasPendingTransactions())

    today = datetime.now(Central_tzinfo()).date()
    yesterday = today + timedelta(days=-1)
    week_ago = today + timedelta(days=-7)
    ten_days_ago = today + timedelta(days=-10)

    # one unprocessed for yesterday
    createPendingTransaction(self.account, 5000000, yesterday, False)

    # one unprocessed for 1 week ago
    createPendingTransaction(self.account, 5000000, week_ago, False)

    # one processed for ten days ago
    createPendingTransaction(self.account, 5000000, ten_days_ago, True)

    # general case - there are some pending transactions that are unprocessed
    self.assertTrue(self.account.hasPendingTransactions())
    # >= 1 unprocessed yesterday
    self.assertTrue(self.account.hasPendingTransactions(transaction_date=yesterday))
    # >= 1 unprocessed 1 week ago
    self.assertTrue(self.account.hasPendingTransactions(transaction_date=week_ago))
    # no unprocessed for 10 days ago
    self.assertFalse(self.account.hasPendingTransactions(transaction_date=ten_days_ago))
    # one processed for 10 days ago
    self.assertTrue(self.account.hasPendingTransactions(transaction_date=ten_days_ago, find_any_status=True))


  def test_calculateBalance(self):
    pass


class TestAccountTransaction(AppEngineTestCase):
  def test_getAmountForPrinting(self):
    pass

  def test_hasPendingTransactions(self):
    pass

