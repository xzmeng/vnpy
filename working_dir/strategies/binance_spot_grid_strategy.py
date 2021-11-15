import decimal
from threading import Thread

from vnpy.trader.constant import Status, Direction
from vnpy.trader.object import AccountData
from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData
)

from time import time
import numpy as np
import time
import decimal
from decimal import Decimal


class BinanceSpotGridStrategy(CtaTemplate):
    """"""
    author = "用Python的交易员"

    base = 'DOGE'
    quote = 'USDT'
    bottom = 0.24
    top = 0.27
    step = 0.006
    quote_size = 11

    precision = 0.0001
    min_trade_amount = 1

    initial_orders_sent = False
    initial_orders_submitted = False

    parameters = ['base', 'quote', 'bottom', 'top', 'step', 'quote_size',
                  'precision', 'min_trade_amount']

    variables = ['initial_orders_sent', 'initial_orders_submitted']

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.initial_order_ids = []
        self.last_tick = None

    def check_balance(self, base_needed, quote_needed):
        main_engine = self.cta_engine.main_engine
        base_account_id = 'BINANCE_SPOT.' + self.base
        quote_account_id = 'BINANCE_SPOT.' + self.quote
        base: AccountData = main_engine.get_account(base_account_id)
        quote: AccountData = main_engine.get_account(quote_account_id)

        available_base = base.balance - base.frozen
        available_quote = quote.balance - quote.frozen

        if available_base < base_needed:
            raise ValueError(
                f'available base: {available_base}, base needed: {base_needed}')
        if available_quote < quote_needed:
            raise ValueError(
                f'available quote: {available_quote}, quote needed: {quote_needed}')

    def round_price(self, price: float) -> float:
        price = Decimal(str(price)).quantize(Decimal(str(self.precision)))
        return float(price)

    def get_volume(self, price: float) -> float:
        volume = Decimal(str(self.quote_size / price)).quantize(
            Decimal(str(self.min_trade_amount)), decimal.ROUND_UP)
        return float(volume)

    def new_order(self, price, direction):
        volume = self.get_volume(price)
        if direction == Direction.LONG:
            order_ids = self.buy(price, volume)
        elif direction == Direction.SHORT:
            order_ids = self.sell(price, volume)
        else:
            order_ids = []
        if not order_ids:
            raise Exception(
                f'下单失败: price: {price}, volume: {volume} direction: {direction}')
        self.initial_order_ids += order_ids

    def init_orders(self, start_price):
        self.write_log('开始初始化网格订单')
        buys = []
        sells = []

        price = start_price
        while price > self.bottom:
            price *= (1 - self.step)
            buys.append(self.round_price(price))

        price = start_price
        while price < self.top:
            price *= (1 + self.step)
            sells.append(self.round_price(price))

        quote_needed = self.quote_size * len(buys)
        base_needed = (self.quote_size / np.array(sells)).sum()

        self.check_balance(base_needed, quote_needed)

        self.new_order(buys[0], Direction.LONG)
        self.new_order(buys[1], Direction.LONG)
        self.new_order(sells[0], Direction.SHORT)
        self.new_order(sells[1], Direction.SHORT)

        for price in buys[2:]:
            self.new_order(price, Direction.LONG)
            time.sleep(0.5)

        for price in sells[2:]:
            self.new_order(price, Direction.SHORT)
            time.sleep(0.5)

        self.initial_orders_sent = True
        self.write_log('网格订单初始化完毕')

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log('初始化策略')
        pass

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.trading = True
        self.write_log('开始策略')
        i = 0
        while self.last_tick is None:
            time.sleep(1)
            i += 1
            if i > 30:
                raise TimeoutError('超时未获取到最新价格')
        start_price = self.last_tick
        self.write_log(f'以{start_price}为开始价格, 启动初始化线程')
        t = Thread(target=self.init_orders, args=(start_price,))
        t.start()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        pass

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.last_tick = tick.last_price

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        pass

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        if order.status == Status.ALLTRADED:
            if order.direction == Direction.LONG:
                self.write_log(
                    f'买单成交 - price: {order.price}, volume: {order.volume}')
                price = self.round_price(order.price * (1 + self.step))
                volume = self.get_volume(price)
                self.write_log(f'卖单下单 - price: {price}, volume: {volume}')
                self.sell(price, volume)
            elif order.direction == Direction.SHORT:
                self.write_log(
                    f'卖单成交 - price: {order.price}, volume: {order.volume}')
                price = self.round_price(order.price * (1 + self.step))
                volume = self.get_volume(price)
                self.write_log(f'买单下单 - price: {price}, volume: {volume}')
                self.buy(price, volume)
        elif order.status == Status.NOTTRADED:
            if not self.initial_orders_submitted:
                order_id = 'BINANCE_SPOT.' + order.orderid
                if order_id not in self.initial_order_ids:
                    self.write_log('Warning: 网格订单未初始化前产生了其他订单')
                self.initial_order_ids.remove(order_id)
                if not self.initial_order_ids and self.initial_orders_sent:
                    self.initial_orders_submitted = True
                    self.write_log('网格初始订单全部挂单成功')

            self.write_log(
                f'下单成功 - price: {order.price}, volume: {order.volume},'
                f'direction: {order.direction}')

        elif order.status == Status.REJECTED:
            self.write_log(f'下单失败 - id: {order.orderid}')
        elif order.status == Status.CANCELLED:
            self.write_log(f'订单撤销 - id: {order.orderid}')

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        pass

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
