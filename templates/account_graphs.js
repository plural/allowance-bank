<script language="JavaScript">

function prepareGoogleVisualizationAPI(callback) {
  google.load("visualization", "1", {packages:["corechart"]});
  google.setOnLoadCallback(callback);
}

function staticUpdateAccountGraphs() { updateAccountGraphs(null); }

function sumArray(data) {
  var sum = 0;
  for (var i = 0; i < data.length; i++) {
    sum += data[i];
  }
  return sum;
}

function keys(data) {
  var keys = [];
  for (var key in data) {
    keys.push(key);
  }
  return keys;
}

function accountSumValuesThrough(data, cutoffDate, keysFilter) {
  var sum = 0;
  for (var transactionDate in data) {
    if (transactionDate <= cutoffDate) {
      for (var transactionType in data[transactionDate]) {
        var shouldAddValue = (keysFilter.length == 0);
        if (!shouldAddValue) {
          for (var i in keysFilter) {
            if (transactionType == keysFilter[i]) {
              shouldAddValue = true;
              break;
            }
          }
        }
        if (shouldAddValue) {
          sum += data[transactionDate][transactionType];
        }
      }
    }
  }
  return sum;
}

// start at the account open date, insert a date at that point
function updateAccountGraphs(ignored_element) {
  // key will be a js date, value will be another hash with transaction type as
  // the key and the amount as the value
  var transactions = {};
  var graphygoodness = document.getElementById('balance_details');

  var openingDate = Date.parse(document.getElementById('open_date').value);
  var openingBalance = parseFloat(document.getElementById('opening_balance').value);

  var allowanceFrequencyElement = document.getElementById('allowance_frequency');
  var allowanceFrequency = allowanceFrequencyElement[allowanceFrequencyElement.selectedIndex].value;
  var allowanceStartDate = Date.parse(document.getElementById('allowance_start_date').value);
  var allowanceAmount = parseFloat(document.getElementById('allowance_amount').value);

  var interestFrequencyElement = document.getElementById('interest_compound_frequency');
  var interestFrequency = interestFrequencyElement[interestFrequencyElement.selectedIndex].value;
  var interestRate = parseFloat(document.getElementById('interest_rate').value);

  if (!(openingDate && openingBalance && allowanceFrequency && allowanceStartDate && allowanceAmount && interestFrequency && interestRate)) {
    document.getElementById('balance_chart').innerHTML = '';
    document.getElementById('interest_chart').innerHTML = '';
    document.getElementById('balance_details').innerHTML = '';
    return;
  }
  var results = '';
  var balance = openingBalance;
  var dates = new Array();
  var principalOnlyAmounts = new Array();
  var balancesWithInterest = new Array();

  // TODO(jgessner): pull in the historical values for the edit page and start graphs from already recorded values, projecting out 1 year, still.
  // put the opening balance in the transactions list
  transactions[openingDate.toISOString()] = {};
  transactions[openingDate.toISOString()]['opening balance'] = openingBalance;
  console.log('Transactions after opening balance...'); console.log(transactions);
  if (allowanceFrequency == 'weekly') {
    console.log('calculating weekly allowance amounts...');
    for (var i = 0; i < 52; i++) {
      allowanceDate = allowanceStartDate.clone();
      allowanceDate.addWeeks(i);
      if (!transactions.hasOwnProperty(allowanceDate.toISOString())) {
        transactions[allowanceDate.toISOString()] = {};
      }
      transactions[allowanceDate.toISOString()]['allowance'] = allowanceAmount;
    }
  } else if (allowanceFrequency == 'monthly') {
    console.log('calculating monthly allowance amounts...');
    for (var i = 0; i < 12; i++) {
      allowanceDate = allowanceStartDate.clone();
      allowanceDate.addMonths(i);
      if (!transactions.hasOwnProperty(allowanceDate.toISOString())) {
        transactions[allowanceDate.toISOString()] = {};
      }
      transactions[allowanceDate.toISOString()]['allowance'] = allowanceAmount;
    }
  }
  console.log('Transactions after allowance...'); console.log(transactions);

  if (interestFrequency == 'weekly') {
    console.log('calculating weekly interest payments...');
    for (var i = 1; i < 52; i++) {
      interestDate = openingDate.clone();
      interestDate.addWeeks(i);
      var balance = accountSumValuesThrough(transactions, interestDate.toISOString(), []);
      console.log('Balance at ' + interestDate.toISOString() + ' == ' + balance);
      var interest = balance * (interestRate/100);
      if (!transactions.hasOwnProperty(interestDate.toISOString())) {
        transactions[interestDate.toISOString()] = {};
      }
      transactions[interestDate.toISOString()]['interest'] = interest;
    }
  } else if (interestFrequency == 'monthly') {
    console.log('calculating monthly interest payments...');
    for (var i = 1; i < 12; i++) {
      interestDate = openingDate.clone();
      interestDate.addMonths(i);
      var balance = accountSumValuesThrough(transactions, interestDate.toISOString(), []);
      console.log('Balance at ' + interestDate.toISOString() + ' == ' + balance);
      var interest = balance * (interestRate/100);
      if (!transactions.hasOwnProperty(interestDate.toISOString())) {
        transactions[interestDate.toISOString()] = {};
      }
      transactions[interestDate.toISOString()]['interest'] = interest;
    }
  }
  console.log('Transactions after interest...'); console.log(transactions);

  var interestOnlyDataTable = new google.visualization.DataTable();
  interestOnlyDataTable.addColumn('date', 'Date');
  interestOnlyDataTable.addColumn('number', 'Interest Earned');

  var dataTable = new google.visualization.DataTable();
  dataTable.addColumn('date', 'Date');
  dataTable.addColumn('number', 'Allowance Only');
  dataTable.addColumn('number', 'Allowance With Interest');
  dataTable.addColumn('number', 'Interest Earned');

  for (var i = 0; i < 12; i++) {
    var graphDate = openingDate.clone();
    graphDate.addMonths(i);
    var allowanceOnlyAmount = accountSumValuesThrough(transactions, graphDate.toISOString(), ['opening balance', 'allowance']);
    var amountWithInterest = accountSumValuesThrough(transactions, graphDate.toISOString(), []);

    dataTable.addRow();
    dataTable.setValue(i, 0, graphDate);
    dataTable.setValue(i, 1, parseFloat(allowanceOnlyAmount.toFixed(2)));
    dataTable.setValue(i, 2, parseFloat(amountWithInterest.toFixed(2)));
    var interestOnlyAmount = accountSumValuesThrough(transactions, graphDate.toISOString(), ['interest']);
    dataTable.setValue(i, 3, parseFloat(interestOnlyAmount.toFixed(2)));
  }
  graphygoodness.innerHTML = results;

  var chart = new google.visualization.LineChart(document.getElementById('balance_chart'));
  chart.draw(dataTable, {chartArea: {left: 50, top: 20}, width: 600, height: 400, title: 'Account Balance Projections'});
}
</script>
