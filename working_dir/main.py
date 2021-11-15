from dotenv import load_dotenv

load_dotenv()

import os

from time import sleep
from logging import INFO

from vnpy.event import EventEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.engine import MainEngine

from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctastrategy.base import EVENT_CTA_LOG
from vnpy_binance import BinanceSpotGateway

SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True

binance_setting = {
    "key": os.environ.get('BINANCE_KEY'),
    "secret": os.environ.get('BINANCE_SECRET'),
    "服务器": "REAL",
    "代理地址": os.environ.get('PROXY_HOST'),
    "代理端口": os.environ.get('PROXY_PORT')
}

SETTINGS["log.file"] = True

event_engine = EventEngine()
main_engine = MainEngine(event_engine)
main_engine.add_gateway(BinanceSpotGateway)
cta_engine = main_engine.add_app(CtaStrategyApp)
main_engine.write_log("主引擎创建成功")

log_engine = main_engine.get_engine("log")
event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
main_engine.write_log("注册日志事件监听")

main_engine.connect(binance_setting, "BINANCE_SPOT")
main_engine.write_log("连接binance")

sleep(5)

cta_engine.init_engine()
main_engine.write_log("CTA引擎初始化完成")

dogegrid_settings = {
    "bottom": 0.2,
    "top": 0.3,
    "step": 0.006,
    "quote_size": 10
}

cta_engine.add_strategy('BinanceSpotGridStrategy', 'dogegrid',
                        'dogeusdt.BINANCE', dogegrid_settings)
cta_engine.init_all_strategies()
main_engine.write_log("CTA策略全部初始化")

sleep(10)

cta_engine.start_all_strategies()
main_engine.write_log("CTA策略全部启动")

while True:
    sleep(5)

# EventEngine _run (tick -> on_tick -> buy -> gateway -> main loop async http)
# EventEngine _timer
# event loop
# main thread
# CtaEngine init thread pool executor
