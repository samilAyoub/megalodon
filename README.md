**What is this?**

A bot to trade futures contracts on Binance.

**How it works?**

We can split how the bot works into three main steps:

1- Analyze the Binance exchange to catch trending markets, by calculating a metric called [ADX](https://www.investopedia.com/articles/trading/07/adx-trend-indicator.asp)

2- If a trending market is caught, then the bot immediately start listening for buy/sell triggers, by using a strategy called [Talon Sniper](https://www.tradingview.com/script/Kt8v4HcD-Talon-Sniper-v1/)

3- If a buy/sell position opened, then the bot starts tracking it and listening for an opposite signal to close it.

N.B: If you wonder why we check if the market trending before going further, because the Talon Sniper strategy is known for its weakness when it is applied to non-trending markets.


**USE THE SOFTWARE AT YOUR OWN RISK. I'M NOT RESPONSIBLE FOR THE TRADING RESULTS. DON'T RISK MONEY YOU CAN'T LOSE.**

Always start by running your account in test trading mode, and don't commit money before you understand how it works and what profit/loss you should expect.

We strongly recommend that you have some knowledge of coding and Python. Do not hesitate to read the source code and understand the mechanism of this bot.

