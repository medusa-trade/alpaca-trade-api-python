import datetime
import pandas as pd
from alpaca_trade_api import polygon
from alpaca_trade_api.polygon import REST
import pytest
import requests_mock
from alpaca_trade_api.polygon.rest import FinancialsReportType, FinancialsSort


@pytest.fixture
def reqmock():
    with requests_mock.Mocker() as m:
        yield m


def endpoint(path, params='', api_version='v1'):
    return 'https://api.polygon.io/{}{}?{}&apiKey=key-id'.format(
        api_version, path, params
    )


def test_polygon(reqmock):
    cli = REST('key-id')

    # Exchanges
    reqmock.get(endpoint('/meta/exchanges'), text='''
    [{"id":0,"type":"TRF","market":"equities","mic":"TFF","name":"Multiple","tape":"-"}]
''')

    exchanges = cli.exchanges()
    assert exchanges[0].id == 0
    assert 'Exchange(' in str(exchanges[0])
    with pytest.raises(AttributeError):
        exchanges[0].foo

    # Symbol Type Map
    reqmock.get(endpoint('/meta/symbol-types'), text='''
{
  "cs": "Common Stock",
  "adr": "American Depository Receipt",
  "cef": "Closed-End Fund",
  "etp": "Exchange Traded Product",
  "reit": "Real Estate Investment Trust",
  "mlp": "Master Limited Partnership",
  "wrt": "Equity WRT",
  "pub": "Public",
  "nyrs": "New York Registry Shares",
  "unit": "Unit",
  "right": "Right",
  "trak": "Tracking stock or targeted stock",
  "ltdp": "Limited Partnership",
  "rylt": "Royalty Trust",
  "mf": "Mutual Fund",
  "pfd": "Preferred Stoc"
}
''')

    tmap = cli.symbol_type_map()
    assert tmap.cs == 'Common Stock'

    # Historic Aggregates V2
    aggs_response = '''
{
  "ticker": "AAPL",
  "status": "OK",
  "adjusted": true,
  "queryCount": 55,
  "resultsCount": 2,
  "results": [
    {
      "o": 173.15,
      "c": 173.2,
      "l": 173.15,
      "h": 173.21,
      "v": 1800,
      "t": 1517529605000
    }
  ]
}'''

    reqmock.get(
        endpoint(
            '/aggs/ticker/AAPL/range/1/day/2018-02-02/2018-02-06',
            params='unadjusted=False', api_version='v2'
        ),
        text=aggs_response)

    reqmock.get(
        endpoint(
            '/aggs/ticker/AAPL/range/1/day/1546300800000/2018-02-06',
            params='unadjusted=False', api_version='v2'
        ),
        text=aggs_response)

    aggs = cli.historic_agg_v2(
        'AAPL', 1, 'day',
        _from='2018-2-2',
        to='2018-2-5'
    )
    assert aggs[0].open == 173.15
    assert len(aggs) == 1
    assert aggs.df.iloc[0].high == 173.21
    with pytest.raises(AttributeError):
        aggs[0].foo

    # test different supported date formats, just make sure they are parsed
    # correctly by the sdk. don't care about the response
    cli.historic_agg_v2(
        'AAPL', 1, 'day',
        _from=datetime.datetime(2018, 2, 2),
        to='2018-2-5'
    )

    # test different supported date formats
    cli.historic_agg_v2(
        'AAPL', 1, 'day',
        _from=datetime.date(2018, 2, 2),
        to='2018-2-5'
    )

    # test different supported date formats
    cli.historic_agg_v2(
        'AAPL', 1, 'day',
        _from=pd.Timestamp('2018-2-2'),
        to='2018-2-5'
    )

    cli.historic_agg_v2(
        'AAPL', 1, 'day',
        _from=pd.Timestamp('2019-01-01').timestamp()*1000,
        to='2018-2-5'
    )

    with pytest.raises(Exception):
        cli.historic_agg_v2(
            'AAPL', 1, 'day',
            _from="bad format",
            to='2018-2-5'
        )

    # Last Trade
    reqmock.get(
        endpoint('/last/stocks/AAPL'),
        text='''
{
  "status": "success",
  "symbol": "AAPL",
  "last": {
    "price": 159.59,
    "size": 20,
    "exchange": 11,
    "cond1": 14,
    "cond2": 16,
    "cond3": 0,
    "cond4": 0,
    "timestamp": 1518086464720
  }
}''')

    trade = cli.last_trade('AAPL')
    assert trade.price == 159.59
    assert trade.timestamp.day == 8

    # Last Quote
    reqmock.get(
        endpoint('/last_quote/stocks/AAPL'),
        text='''
{
  "status": "success",
  "symbol": "AAPL",
  "last": {
    "askprice": 159.59,
    "asksize": 2,
    "askexchange": 11,
    "bidprice": 159.45,
    "bidsize": 20,
    "bidexchange": 12,
    "timestamp": 1518086601843
  }
}''')

    quote = cli.last_quote('AAPL')
    assert quote.askprice == 159.59
    assert quote.timestamp.day == 8

    # Condition Map
    reqmock.get(
        endpoint('/meta/conditions/trades'),
        text='''
{
  "1": "Regular",
  "2": "Acquisition",
  "3": "AveragePrice",
  "4": "AutomaticExecution"
}''')

    cmap = cli.condition_map()
    assert cmap._raw['1'] == 'Regular'

    # Company
    reqmock.get(
        endpoint('/meta/symbols/company', 'symbols=AAPL'),
        text='''[{"symbol": "AAPL"}]''',
    )

    ret = cli.company('AAPL')
    assert ret.symbol == 'AAPL'
    ret = cli.company(['AAPL'])
    assert ret['AAPL'].symbol == 'AAPL'

    # Dividends
    reqmock.get(
        endpoint('/meta/symbols/dividends', 'symbols=AAPL'),
        text='''{"AAPL": [{"qualified": "Q"}]}''',
    )
    ret = cli.dividends('AAPL')
    assert ret[0].qualified == 'Q'
    ret = cli.dividends(['AAPL'])
    assert ret['AAPL'][0].qualified == 'Q'

    # Splits
    reqmock.get(
        endpoint('/reference/splits/AAPL', api_version='v2'),
        text='''{"results": [{"forfactor": 1}]}''',
    )
    ret = cli.splits('AAPL')
    assert ret[0].forfactor == 1

    # Earnings
    reqmock.get(
        endpoint('/meta/symbols/earnings', 'symbols=AAPL'),
        text='''{"AAPL": [{"actualEPS": 1}]}''',
    )
    ret = cli.earnings('AAPL')
    assert ret[0].actualEPS == 1
    ret = cli.earnings(['AAPL'])
    assert ret['AAPL'][0].actualEPS == 1

    # Financials
    reqmock.get(
        endpoint('/meta/symbols/financials', 'symbols=AAPL'),
        text='''{"AAPL": [{"reportDateStr": "2018-09-01"}]}''',
    )
    ret = cli.financials('AAPL')
    assert ret[0].reportDateStr == '2018-09-01'
    ret = cli.financials(['AAPL'])
    assert ret['AAPL'][0].reportDateStr == '2018-09-01'

    # Financials v2
    reqmock.get(
        endpoint('/reference/financials/AAPL', api_version='v2'),
        text='''
        {
    "status": "OK",
    "results": [
        {
            "earningsPerBasicShare": 11.97,
            "payoutRatio": 0.251,
            "updated": "2020-05-01",
            "workingCapital": 57101000000,
            "earningsBeforeInterestTaxesDepreciationAmortizationUSD":
            78284000000,
            "priceEarnings": 20.003,
            "dividendYield": 0.012,
            "period": "Y",
            "earningsBeforeInterestTaxesDepreciationAmortization": 78284000000,
            "earningBeforeInterestTaxesUSD": 65737000000,
            "preferredDividendsIncomeStatementImpact": 0,
            "dividendsPerBasicCommonShare": 3,
            "earningsBeforeTax": 65737000000,
            "dateKey": "2019-10-31",
            "earningsPerDilutedShare": 11.89,
            "earningsPerBasicShareUSD": 11.97,
            "ticker": "AAPL",
            "earningBeforeInterestTaxes": 65737000000
        },
        {
            "earningsPerBasicShare": 12.01,
            "enterpriseValueOverEBIT": 14,
            "workingCapital": 14473000000,
            "priceToBookValue": 8.928,
            "weightedAverageSharesDiluted": 5000109000,
            "period": "Y",
            "priceSales": 3.602,
            "earningsBeforeInterestTaxesDepreciationAmortization": 83806000000,
            "tradeAndNonTradeReceivables": 48995000000,
            "totalLiabilities": 258578000000,
            "earningsPerDilutedShare": 11.91,
            "calendarDate": "2018-12-31",
            "earningsPerBasicShareUSD": 12.01,
            "earningsBeforeTax": 72903000000,
            "priceEarnings": 16.069,
            "netIncomeCommonStockUSD": 59531000000,
            "netIncomeCommonStock": 59531000000,
            "enterpriseValueOverEBITDA": 12.472,
            "earningBeforeInterestTaxesUSD": 72903000000,
            "effectOfExchangeRateChangesOnCash": 0,
            "updated": "2020-05-01",
            "earningsBeforeInterestTaxesDepreciationAmortizationUSD":
            83806000000,
            "netIncome": 59531000000,
            "enterpriseValue": 1045194782820,
            "tradeAndNonTradePayables": 55888000000,
            "dateKey": "2018-11-05",
            "ticker": "AAPL",
            "weightedAverageShares": 4955377000,
            "preferredDividendsIncomeStatementImpact": 0,
            "earningBeforeInterestTaxes": 72903000000
        }
    ]
}
        ''',
    )

    ret = cli.financials_v2('AAPL',
                            2,
                            FinancialsReportType.Y,
                            FinancialsSort.CalendarDateDesc)

    assert len(ret) == 2
    assert type(ret) == polygon.entity.Financials
    assert type(ret[0]) == polygon.entity.Financial
    assert ret[0].ticker == "AAPL"

    # News
    reqmock.get(
        endpoint('/meta/symbols/AAPL/news'),
        text='''[{"title": "Apple News"}]''',
    )
    ret = cli.news('AAPL')
    assert ret[0].title == 'Apple News'

    with pytest.raises(ValueError):
        cli.company(['AAPL'] * 51)

    # paginated symbol list
    reqmock.get(
        endpoint('/reference/tickers', api_version='v2'),
        text='''
{"page": 1, "perPage": 30, "count": 32657, "status": "OK", "tickers": [
  {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "market": "STOCKS",
    "locale": "US",
    "currency": "USD",
    "active": true,
    "primaryExch": "NGS",
    "type": "cs",
    "codes": {
      "cik": "0000320193",
      "figiuid": "EQ0010169500001000",
      "scfigi": "BBG001S5N8V8",
      "cfigi": "BBG000B9XRY4",
      "figi": "BBG000B9Y5X2"
    },
    "updated": "2019-01-15T05:21:28.437Z",
    "url": "https://api.polygon.io/v2/reference/tickers/AAPL"
  },
  {
    "ticker": "GOOG",
    "name": "Google Inc.",
    "market": "STOCKS",
    "locale": "US",
    "currency": "USD",
    "active": true,
    "primaryExch": "NGS",
    "type": "cs",
    "codes": {
      "cik": "0000320193",
      "figiuid": "EQ0010169500001000",
      "scfigi": "BBG001S5N8V8",
      "cfigi": "BBG000B9XRY4",
      "figi": "BBG000B9Y5X2"
    },
    "updated": "2019-01-15T05:21:28.437Z",
    "url": "https://api.polygon.io/v2/reference/tickers/GOOG"
  }
]}''')
    cli.symbol_list_paginated(1, 2)
    # nothing to assert in the mock data. jsut checking params are parsed
    # correctly
