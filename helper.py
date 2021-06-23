from binance.client import Client
import pandas as pd
import sys, os
import config as cfg
import math
from datetime import datetime, timedelta
import time
import numpy as np
import talib
from binance.helpers import round_step_size
from binance_f import RequestClient


def blockPrint():
    sys.stdout = open(os.devnull, 'w')


def enablePrint():
    sys.stdout = sys.__stdout__


# create a binance request client
def init_client():
    client = Client(api_key=cfg.getPublicKey(), api_secret=cfg.getPrivateKey())
    return client


# get the current market price
def get_market_price(client, _market):
    price = client.futures_mark_price(symbol=_market)
    price = float(price['markPrice'])
    return price


# Get futures balances. We are interested in USDT by default as this is what we use as margin.
def get_futures_balance(client, _asset="USDT"):
    balances = client.futures_account_balance()
    asset_balance = 0
    for balance in balances:
        if balance['asset'] == _asset:
            asset_balance = balance['balance']
            break
    return asset_balance


# Init the market we want to trade. First we change leverage type
# then we change margin type
def initialise_futures(client, _market, _leverage=1, _margin_type="ISOLATED"):
    try:
        client.futures_change_leverage(symbol=_market, leverage=_leverage)
        client.futures_change_margin_type(symbol=_market,
                                          marginType=_margin_type)
    except Exception as e:
        if "No need to change margin type" in str(e):
            return
        msg = "Adjust margin/leaverage: " + str(e)
        raise Exception(msg)


# get all of our open orders in a market
def get_orders(client, _market):
    orders = client.futures_get_open_orders(symbol=_market)
    return orders, len(orders)


# Execute an order, this can open and close a trade
def execute_order(
    client,
    _market,
    _type="MARKET",
    _side="BUY",
    _position_side="BOTH",
    _qty=1.0,
):
    client.futures_create_order(
        symbol=_market,
        type=_type,
        side=_side,
        positionSide=_position_side,
        quantity=str(_qty),
    )


# close all opened position
def close_all_positions(client):
    positions = get_all_positons(client)
    for position in positions:
        _market = position['symbol']
        _qty = float(position['positionAmt'])
        if int(_qty) != 0:
            _side = "BUY"
            if _qty > 0.0:
                _side = "SELL"

            if _qty < 0.0:
                _qty = _qty * -1

            _qty = str(_qty)

            execute_order(client, _market=_market, _qty=_qty, _side=_side)


# close opened positions
def close_position_by_market(client, _market):
    position = get_positon_by_market(client, _market)
    _qty = float(position['positionAmt'])
    if int(_qty) != 0:
        _side = "BUY"
        if _qty > 0.0:
            _side = "SELL"

        if _qty < 0.0:
            _qty = _qty * -1

        _qty = str(_qty)

        execute_order(client, _market=_market, _qty=_qty, _side=_side)


def cancel_all_open_orders(client):
    client.futures_cancel_all_open_orders()


def cancel_open_orders_by_market(client, _market):
    client.futures_cancel_all_open_orders(symbol=_market)


# get the liquidation price of the position we are in. - We don't use this - be careful!
def get_liquidation(client, _market):
    position = get_positon_by_market(client, _market)
    return position['liquidationPrice']


# Get the entry price of the position the bot is in
def get_entry(client, _market):
    position = get_positon_by_market(client, _market)
    return position['entryPrice']


# calculate how big a position we can open with the margin we have and the leverage we are using
def calculate_position_size(client, _market, usdt_balance=1.0, _leverage=1):
    price = get_market_price(client, _market)
    usdt_balance = float(usdt_balance)
    qty = (usdt_balance / price) * _leverage
    qty = qty * 0.99
    return qty


# Create a trailing stop to close our order if something goes bad, lock in profits or if the trade goes against us!
def submit_trailing_order(
    client,
    _market,
    _type="TRAILING_STOP_MARKET",
    _side="BUY",
    _qty=1.0,
    _callbackRate=4,
):

    client.futures_create_order(
        symbol=_market,
        type=_type,
        side=_side,
        callbackRate=_callbackRate,
        quantity=_qty,
        workingType="CONTRACT_PRICE",
    )


# get the precision of the market, this is needed to avoid errors when creating orders
def get_market_precision(client, _market):
    market_data = client.get_symbol_info(_market)
    step_size = 0.01
    for filter in market_data['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            step_size = float(filter['stepSize'])
    precision = int(round(-math.log(step_size / 0.01, 10), 0))
    return precision


def get_market_precision_v2(_market):
    client = RequestClient(api_key=cfg.getPublicKey(),
                           secret_key=cfg.getPrivateKey(),
                           url=cfg.getBotSettings().api_url)
    market_data = client.get_exchange_information()
    precision = 3
    for market in market_data.symbols:
        if market.symbol == _market:
            precision = market.quantityPrecision
            break
    return precision


# round the position size we can open to the precision of the market
def round_to_precision(_qty, _precision):
    return float(round(_qty, _precision))


# convert from client candle data into a set of lists
def convert_candles(candles):
    o = []
    h = []
    l = []
    c = []
    v = []

    for candle in candles:
        o.append(float(candle[1]))
        h.append(float(candle[2]))
        l.append(float(candle[3]))
        c.append(float(candle[4]))
        v.append(float(candle[5]))

    return o, h, l, c, v


# convert list candle data into list of heikin ashi candles
def construct_heikin_ashi(o, h, l, c):
    h_o = []
    h_h = []
    h_l = []
    h_c = []

    for i, v in enumerate(o):

        close_price = (o[i] + h[i] + l[i] + c[i]) / 4

        if i == 0:
            open_price = close_price
        else:
            open_price = (h_o[-1] + h_c[-1]) / 2

        high_price = max([h[i], close_price, open_price])
        low_price = min([l[i], close_price, open_price])

        h_o.append(open_price)
        h_h.append(high_price)
        h_l.append(low_price)
        h_c.append(close_price)

    return h_o, h_h, h_l, h_c


def get_all_positons(client):
    positions = client.futures_position_information()
    return positions


def get_positon_by_market(client, market):
    position = client.futures_position_information(symbol=market)
    return position[0]  # We have only one position


def check_in_position(client, market):
    position = get_positon_by_market(client, market)

    in_position = False

    if float(position['positionAmt']) != 0.0:
        in_position = True

    return in_position


def open_position(
    client,
    market="BTCUSDT",
    leverage=3,
    order_side="BUY",
    stop_side="SELL",
    _callbackRate=2.0,
):
    initialise_futures(client, _market=market, _leverage=leverage)
    blockPrint()
    qty = calculate_position(client, market, _leverage=leverage)
    enablePrint()
    execute_order(client, _market=market, _side=order_side, _qty=qty)
    market_price = get_market_price(client, _market=market)
    if order_side == "BUY":
        side = 1
    elif order_side == "SELL":
        side = -1
    msg = f"{order_side}: {qty} ${market_price} using x{leverage} leverage"
    # close any open trailing stops we have
    client.futures_cancel_all_open_orders(symbol=market)
    time.sleep(3)
    log_trade(
        _qty=qty,
        _market=market,
        _leverage=leverage,
        _side=side,
        _cause="Signal Change",
        _trigger_price=0,
        _market_price=market_price,
        _type=order_side,
    )
    # Let the order execute and then create a trailing stop market order.
    time.sleep(3)
    submit_trailing_order(client,
                          _market=market,
                          _qty=qty,
                          _side=stop_side,
                          _callbackRate=_callbackRate)

    return qty, side, msg


def handle_siganl(client,
                  entry,
                  market="BTCUSDT",
                  leverage=3,
                  _callbackRate=2.0):
    '''
    Handle a given singal.

    entry:array: signals across multiple time scales. signal of -1 is SHORT, 1 is LONG and 0 is Not confirmed.
    '''

    # SELL signals are confirmed across given time scales
    if entry[-2] == -1:
        return open_position(
            client,
            market=market,
            leverage=leverage,
            order_side="SELL",
            stop_side="BUY",
            _callbackRate=_callbackRate,
        )

    # BUY signals are confirmed across given time scales
    elif entry[-2] == 1:
        return open_position(
            client,
            market=market,
            leverage=leverage,
            order_side="BUY",
            stop_side="SELL",
            _callbackRate=_callbackRate,
        )


# create a dataframe for our candles
def to_dataframe(o, h, l, c, v):
    df = pd.DataFrame()

    df["open"] = o
    df["high"] = h
    df["low"] = l
    df["close"] = c
    df["volume"] = v

    return df


# Exponential moving avg - unused
def ema(s, n):
    s = np.array(s)
    out = []
    j = 1

    # get n sma first and calculate the next n period ema
    sma = sum(s[:n]) / n
    multiplier = 2 / float(1 + n)
    out.append(sma)

    # EMA(current) = ( (Price(current) - EMA(prev) ) x Multiplier) + EMA(prev)
    out.append(((s[n] - sma) * multiplier) + sma)

    # now calculate the rest of the values
    for i in s[n + 1:]:
        tmp = ((i - out[j]) * multiplier) + out[j]
        j = j + 1
        out.append(tmp)

    return np.array(out)


# Avarage true range function used by our trading strat
def avarage_true_range(high, low, close):

    atr = []

    for i, v in enumerate(high):
        if i != 0:
            value = np.max([
                high[i] - low[i],
                np.abs(high[i] - close[i - 1]),
                np.abs(low[i] - close[i - 1]),
            ])
            atr.append(value)
    return np.array(atr)


# Our trading strategy - it takes in heikin ashi open, high, low and close data and returns a list of signal values
# signals are -1 for short, 1 for long and 0 for do nothing
def trading_signal(h_o, h_h, h_l, h_c, use_last=False):
    factor = 1
    pd = 1

    hl2 = (np.array(h_h) + np.array(h_l)) / 2
    hl2 = hl2[1:]

    atr = avarage_true_range(h_h, h_l, h_c)

    up = hl2 - (factor * atr)
    dn = hl2 + (factor * atr)

    trend_up = [0]
    trend_down = [0]

    for i, v in enumerate(h_c[1:]):
        if i != 0:

            if h_c[i - 1] > trend_up[i - 1]:
                trend_up.append(np.max([up[i], trend_up[i - 1]]))
            else:
                trend_up.append(up[i])

            if h_c[i - 1] < trend_down[i - 1]:
                trend_down.append(np.min([dn[i], trend_down[i - 1]]))
            else:
                trend_down.append(dn[i])

    trend = []
    last = 0
    for i, v in enumerate(h_c):
        if i != 0:
            if h_c[i] > trend_down[i - 1]:
                tr = 1
                last = tr
            elif h_c[i] < trend_up[i - 1]:
                tr = -1
                last = tr
            else:
                tr = last
            trend.append(tr)

    entry = [0]
    last = 0
    for i, v in enumerate(trend):
        if i != 0:
            if trend[i] == 1 and trend[i - 1] == -1:
                entry.append(1)
                last = 1

            elif trend[i] == -1 and trend[i - 1] == 1:
                entry.append(-1)
                last = -1

            else:
                if use_last:
                    entry.append(last)
                else:
                    entry.append(0)

    return entry


# get the data from the market, create heikin ashi candles and then generate signals
# return the signals to the bot
def get_signal(client, _market, _period="15m", use_last=False):
    candles = client.futures_klines(symbol=_market, interval=_period)
    o, h, l, c, v = convert_candles(candles)
    h_o, h_h, h_l, h_c = construct_heikin_ashi(o, h, l, c)
    ohlcv = to_dataframe(h_o, h_h, h_l, h_c, v)
    entry = trading_signal(h_o, h_h, h_l, h_c, use_last)
    return entry


# get signal that is confirmed across multiple time scales
def get_multi_scale_signal(client, _market, _periods=["1m"]):

    signals = np.zeros(499)
    use_last = True

    for i, v in enumerate(_periods):

        _signal = get_signal(client, _market, _period=v, use_last=use_last)
        signals = signals + np.array(_signal)

    signals = signals / len(_periods)

    trade_signal = []

    for i, v in enumerate(list(signals)):

        if v == -1:
            trade_signal.append(-1)
        elif v == 1:
            trade_signal.append(1)
        else:
            trade_signal.append(0)
    return trade_signal


# calculate a rounded position size for the bot, based on current USDT holding, leverage and market
def calculate_position(client, _market, _leverage=1):
    usdt = get_futures_balance(client, _asset="USDT")
    quantity = 0.0
    qty = calculate_position_size(client,
                                  usdt_balance=usdt,
                                  _market=_market,
                                  _leverage=_leverage)
    precision_v2 = get_market_precision_v2(_market=_market)
    quantity = round_to_precision(qty, precision_v2)
    return quantity


# function for logging trades to csv for later analysis
def log_trade(
    _qty=0,
    _market="BTCUSDT",
    _leverage=1,
    _side="long",
    _cause="signal",
    _trigger_price=0,
    _market_price=0,
    _type="exit",
):
    df = pd.read_csv("trade_log.csv")
    df2 = pd.DataFrame()
    df2["date"] = [str(datetime.now())]
    df2["market"] = [_market]
    df2["qty"] = [_qty]
    df2["leverage"] = [_leverage]
    df2["cause"] = [_cause]
    df2["side"] = [_side]
    df2["trigger_price"] = [_trigger_price]
    df2["market_price"] = [_market_price]
    df2["type"] = [_type]

    df = df.append(df2, ignore_index=True)
    df.to_csv("trade_log.csv", index=False)


def get_valid_market(client, adx_threshold=25, volume_threshold=200000000.00):
    """
    Get a valid market; trending with a high volume.
    """
    import random
    info = client.futures_exchange_info()
    item = random.choice(info['symbols'])
    symbol, contractType, marginAsset = item['symbol'], item[
        'contractType'], item['marginAsset']
    if (contractType == 'PERPETUAL' and marginAsset == 'USDT'):
        is_trend_, adx_15min, adx_5min = is_trend(client, symbol,
                                                  adx_threshold)
        is_high_volume_, volume = is_high_volume(client, symbol,
                                                 volume_threshold)
        if is_trend_ and is_high_volume_:
            return symbol


def is_high_volume(client, market, volume_threshold):
    if market != None:
        ticker = client.futures_ticker(symbol=market)
        volume = float(ticker['quoteVolume'])
        if volume >= volume_threshold:
            return True, volume
        else:
            return False, volume


def is_trend(client, market, adx_threshold):
    """
    Check if a given market 
    """
    adx_15min_ = adx_15min(client, market)
    adx_5min_ = adx_5min(client, market)
    if adx_15min_ >= adx_threshold and adx_5min_ >= adx_threshold:
        return True, adx_5min_, adx_15min_
    else:
        return False, adx_5min_, adx_15min_


def is_volatile(client, market, atr_threshold):
    """
    Check if a given market is volatile
    """
    if (atr_15min(client, market) >= atr_threshold
            and atr_5min(client, market) >= atr_threshold):
        return True
    else:
        return False


def adx_5min(client, market, timeperiod=14):
    """
    Calculate current ADX14 of a given market in 5min based kline.
    """
    candles_5min = client.futures_klines(
        symbol=market, interval=Client.KLINE_INTERVAL_5MINUTE)

    candles_5min_arr = np.array(candles_5min).astype("float64")

    high = candles_5min_arr[:, 2]
    low = candles_5min_arr[:, 3]
    close = candles_5min_arr[:, 4]

    adx = talib.ADX(high, low, close, timeperiod=timeperiod)

    return adx[-2]


def adx_15min(client, market, timeperiod=14):
    """
    Calculate current ADX14 of a given market in 15min based kline.
    """

    candles_15min = client.futures_klines(
        symbol=market, interval=Client.KLINE_INTERVAL_15MINUTE)

    candles_15min_arr = np.array(candles_15min).astype("float64")

    high = candles_15min_arr[:, 2]
    low = candles_15min_arr[:, 3]
    close = candles_15min_arr[:, 4]

    adx = talib.ADX(high, low, close, timeperiod=timeperiod)

    return adx[-2]


def atr_15min(client, market, timeperiod=14):
    """
    Calculate current ATR14 of a given market in 15min based kline.
    """

    candles_15min = client.futures_continous_klines(
        symbol=market,
        contractType='PERPETUAL',
        interval=Client.KLINE_INTERVAL_15MINUTE)

    candles_15min_arr = np.array(candles_15min).astype("float64")

    high = candles_15min_arr[:, 2]
    low = candles_15min_arr[:, 3]
    close = candles_15min_arr[:, 4]

    atr = talib.ATR(high, low, close, timeperiod=timeperiod)

    return atr[-2]


def atr_5min(client, market, timeperiod=14):
    """
    Calculate current ATR14 of a given market in 5min based kline.
    """

    candles_5min = client.futures_continous_klines(
        symbol=market,
        contractType='PERPETUAL',
        interval=Client.KLINE_INTERVAL_5MINUTE)

    candles_5min_arr = np.array(candles_5min).astype("float64")

    high = candles_5min_arr[:, 2]
    low = candles_5min_arr[:, 3]
    close = candles_5min_arr[:, 4]

    atr = talib.ATR(high, low, close, timeperiod=timeperiod)

    return atr[-2]


if __name__ == '__main__':
    client = init_client()
    while True:
        market = get_valid_market(client,
                                  adx_threshold=30,
                                  volume_threshold=200000000.00)
        if market != None:
            print(market)
            break