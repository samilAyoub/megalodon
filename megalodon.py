import json
import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from threading import Thread

from binance.exceptions import BinanceAPIException
from requests.exceptions import RequestException

import config as cfg
import helper as h

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%y-%m-%d %H:%M:%S',
    level=logging.INFO)

logger = logging.getLogger('bot')


class Megalodon():
    def __init__(self):

        signal.signal(signal.SIGTERM, self.signal_term_handler)

        # Connect to the binance api and produce a client
        self.client = h.init_client()

        # Load settings from settings.json
        settings = cfg.getBotSettings()
        self.leverage = int(settings.leverage)
        self.margin_type = settings.margin_type
        self.confirmation_periods = settings.trading_periods.split(",")
        self.trailing_percentage = float(settings.trailing_percentage)
        self.adx_threshold = float(settings.market.adx_threshold)
        self.volume_threshold = float(settings.market.volume_threshold)
        self.market_time_out_minutes = float(
            settings.market.market_time_out_minutes)

        # global values used by bot to keep track of state
        self.market = None
        self.side = 0
        self.qty = 0.0
        self.last_trend_check = None

    def start(self):
        logger.info("Bot started.")
        while True:
            try:
                while self.market == None:
                    self.look_for_market()
                self.check_signal()
                # Market detected but, no BUY or SELL detected yet.
                if self.side == 0:
                    # if listning last more then TIME_TO_WAIT_NEXT_MARKET_TREND_MIN then a check for trending market performed again
                    waiting_time_min = ((
                        (datetime.now() -
                         self.last_trend_check).total_seconds()) / 60)
                    if waiting_time_min >= self.market_time_out_minutes:
                        logger.info('%s: %s min ended, market reset.',
                                    self.market,
                                    str(self.market_time_out_minutes))
                        self.market = None
                        self.side = 0
                        continue

                # Market detected and (BUY/SELL) postion oppend.
                else:
                    # if trailing stop tiggered and therefor the postion closed
                    position_active = h.check_in_position(
                        self.client, self.market)
                    if position_active == False:
                        # close any open trailing stops we have one
                        h.cancel_open_orders_by_market(self.client,
                                                       _market=self.market)
                        time.sleep(3)
                        logger.info('%s : Trailing Stop Triggered.',
                                    self.market)
                        h.log_trade(_qty=self.qty,
                                    _market=self.market,
                                    _leverage=self.leverage,
                                    _side=self.side,
                                    _cause="Signal Change",
                                    _market_price=h.get_market_price(
                                        self.client, self.market),
                                    _type="Trailing Stop")
                        self.market = None
                        self.self = 0

                time.sleep(60)

            except (RequestException, BinanceAPIException) as e:
                logger.error(e, exc_info=True)
                logger.info('retry ... ')
                continue

            except KeyboardInterrupt:
                logger.error("Keyboard interrupt catched.")
                break

            except:
                logger.error("uncaught exception: %s", traceback.format_exc())
                break

        self.stop()

    def look_for_market(self):
        if self.market == None:
            self.market = h.get_valid_market(self.client, self.adx_threshold,
                                             self.volume_threshold)
            self.last_trend_check = datetime.now()
            if self.market != None:
                logger.info('Trend market detected: %s', self.market)
                # Initialise the market leverage and margin type.
                h.initialise_futures(self.client,
                                     _market=self.market,
                                     _leverage=self.leverage,
                                     _margin_type=self.margin_type)

    def check_signal(self):
        if self.market != None:
            # generate signal data for the last 500 candles
            entry = h.get_multi_scale_signal(
                self.client,
                _market=self.market,
                _periods=self.confirmation_periods)

            # Signal changed
            if entry[-2] != self.side:
                # No position oppened yet
                if self.side == 0:
                    self.qty, self.side, msg = h.handle_siganl(
                        self.client, entry, self.market, self.leverage,
                        self.trailing_percentage)
                    logger.info('%s: Position opend: %s', self.market, msg)

                # We are an opposit position
                else:
                    h.close_position_by_market(self.client,
                                               _market=self.market)
                    h.cancel_open_orders_by_market(self.client,
                                                   _market=self.market)
                    time.sleep(3)
                    logger.info(
                        '%s : Signal changed from %s to %s, current postion closed.',
                        self.market, str(self.side), str(entry[-2]))
                    h.log_trade(_qty=self.qty,
                                _market=self.market,
                                _leverage=self.leverage,
                                _side=self.side,
                                _cause="Signal Change",
                                _market_price=h.get_market_price(
                                    self.client, self.market),
                                _type="EXIT")
                    self.side = 0

    def stop(self):
        if (self.side != 0):
            # close any open positions
            h.close_position_by_market(self.client, _market=self.market)
            # close any open trailing stops
            h.cancel_open_orders_by_market(self.client, _market=self.market)
            time.sleep(3)
            logger.warning(
                'All open positions closed and all open orders canceled.')
        logger.warning('Bot stopped.')
        os._exit(0)

    def signal_term_handler(self, signal, frame):
        logger.warning('SIGTERM signal received.')
        self.stop()


if __name__ == '__main__':
    Megalodon().start()
