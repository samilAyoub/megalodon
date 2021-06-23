import unittest
from binance.client import Client
import bot.helper as helper
import config_test as cfg
from binance.exceptions import BinanceAPIException


class TestHelper(unittest.TestCase):
    def setUp(self):
        self.client = Client(api_key=cfg.getPublicKey(),
                             api_secret=cfg.getPrivateKey(),
                             testnet=False)
        from binance_f import RequestClient
        self.client_v2 = RequestClient(api_key=cfg.getPublicKey(),
                                       secret_key=cfg.getPrivateKey(),
                                       url=cfg.getBotSettings().api_url)
        super().setUp()

    def tearDown(self):
        self.client = None

    # Basic test
    # If market symbol incorrect, then an exception should raises
    # If market symbol is correct, then No exception should raises, and valid value should be returned
    def basic(self, _func):
        with self.assertRaises(BinanceAPIException):
            _func(self.client, _market='UNCORRECT')
        try:
            returned_value = _func(self.client, _market='BTCUSDT')
            msg = _func.__name__ + ' return None even if the market is correct!'
            self.assertIsNotNone(returned_value, msg)
        except:
            msg = _func.__name__ + ' raised exception unexpectedly!'
            self.fail(msg)

    # get_market_price()
    def test_basic_get_market_price(self):
        self.basic(_func=helper.get_market_price)

    # get_futures_balance()
    # initialise_futures()
    def test_initialise_futures(self):
        helper.initialise_futures(self.client,
                                  _market='BTCUSDT',
                                  _leverage=1,
                                  _margin_type="ISOLATED")
        expeced_leverage = 1
        expected_margin_type = True  # is isolated
        infos = self.client.futures_account(symbol='BTCUSDT')
        positions = infos['positions']
        for position in positions:
            if position['symbol'] == 'BTCUSDT':
                self.assertEqual(expeced_leverage, int(position['leverage']))
                self.assertEqual(expected_margin_type, position['isolated'])

    def test_initialise_futures_change_leverage_and_margine(self):
        helper.initialise_futures(self.client,
                                  _market='BTCUSDT',
                                  _leverage=1,
                                  _margin_type="ISOLATED")

        helper.initialise_futures(self.client,
                                  _market='BTCUSDT',
                                  _leverage=10,
                                  _margin_type="CROSSED")

        expeced_leverage = 10
        expected_margin_type = False  # is isolated
        infos = self.client.futures_account(symbol='BTCUSDT')
        positions = infos['positions']
        for position in positions:
            if position['symbol'] == 'BTCUSDT':
                self.assertEqual(expeced_leverage, int(position['leverage']))
                self.assertEqual(expected_margin_type, position['isolated'])

    # get_orders()
    def test_get_orders(self):
        self.basic(_func=helper.get_orders)

    # execute_order()
    # close_all_positions()
    # close_positions_by_market()
    # get_liquidation()
    # get_entry()
    # calculate_position_size()
    # submit_trailing_order()

    def test_get_market_precision(self):
        precision = helper.get_market_precision(self.client, 'SUSHIUSDT')
        precision_v2 = helper.get_market_precision_v2(self.client_v2,
                                                      'SUSHIUSDT')
        self.assertEqual(precision, 0)

    # round_to_precision()
    # convert_candles()
    # construct_heikin_ashi()
    # get_all_positons()
    # get_positon_by_market()
    # check_in_position()
    # open_position()
    # handle_siganl()
    # ema()
    # avarage_true_range()
    # trading_signal()
    # get_signal()
    # get_multi_scale_signal()
    # calculate_position()
    # get_trend_market()
    # is_trend()
    # adx_5min()
    # adx_15min


if __name__ == '__main__':
    unittest.main()