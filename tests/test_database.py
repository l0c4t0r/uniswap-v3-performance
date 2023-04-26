import sys
import os
import datetime as dt
import logging
import asyncio


logging.basicConfig(
    format="[%(asctime)s:%(levelname)s:%(name)s]:%(message)s",
    datefmt="%Y/%m/%d %I:%M:%S",
    level=logging.INFO,
)

# append parent directory pth
CURRENT_FOLDER = os.path.dirname(os.path.realpath(__file__))
PARENT_FOLDER = os.path.dirname(CURRENT_FOLDER)
sys.path.append(PARENT_FOLDER)


from v3data.enums import Protocol, Chain, QueryType
from v3data.config import (
    MONGO_DB_URL,
    GAMMA_SUBGRAPH_URLS,
    DEFAULT_TIMEZONE,
    DEX_HYPEPOOL_SUBGRAPH_URLS,
)

from database.collection_endpoint import (
    db_returns_manager,
    db_static_manager,
    db_allData_manager,
    db_allRewards2_manager,
    db_aggregateStats_manager,
)

from v3data.common.analytics import get_hype_data

from v3data.common import hypervisor, users
from v3data.common.aggregate_stats import AggregateStats
import database_feeder

logger = logging.getLogger(__name__)


async def test_put_data_to_Mongodb_v1():
    # create a chain protocol list
    protocols = Protocol
    chains_protocols = [
        (chain, protocol)
        for protocol in protocols
        for chain in GAMMA_SUBGRAPH_URLS[protocol].keys()
    ]
    requests = list()

    # returns requests
    returns_manager = db_returns_manager(mongo_url=MONGO_DB_URL)
    requests += [
        returns_manager.feed_db(chain=chain, protocol=protocol)
        for chain, protocol in chains_protocols
    ]

    # static requests
    static_manager = db_static_manager(mongo_url=MONGO_DB_URL)
    requests += [
        static_manager.feed_db(chain=chain, protocol=protocol)
        for chain, protocol in chains_protocols
    ]

    # AllData requests
    allData_manager = db_allData_manager(mongo_url=MONGO_DB_URL)
    requests += [
        allData_manager.feed_db(chain=chain, protocol=protocol)
        for chain, protocol in chains_protocols
    ]

    # allRewards2 requests
    allRewards2_manager = db_allRewards2_manager(mongo_url=MONGO_DB_URL)
    requests += [
        allRewards2_manager.feed_db(chain=chain, protocol=protocol)
        for chain, protocol in chains_protocols
    ]

    # aggregatedStats requests
    aggregatedStats_manager = db_aggregateStats_manager(mongo_url=MONGO_DB_URL)
    requests += [
        aggregatedStats_manager.feed_db(chain=chain, protocol=protocol)
        for chain, protocol in chains_protocols
    ]

    # execute queries
    await asyncio.gather(*requests)


async def test_put_historicData_to_Mongodb():
    # force period
    periods = {
        "daily": [1],
        "weekly": [7],
        "monthly": [30],
    }

    await database_feeder.feed_database_with_historic_data(
        from_datetime=dt.datetime(2022, 12, 1, 0, 0, tzinfo=dt.timezone.utc),
        process_quickswap=True,
        periods=periods,
    )


async def test_put_historicData_to_Mongodb_vExpert(
    chain=Chain.POLYGON, periods=[1], process_quickswap=True
):
    returns_manager = db_returns_manager(mongo_url=MONGO_DB_URL)
    requests = [
        returns_manager.feed_db(chain=chain, protocol=Protocol.UNISWAP, periods=periods)
    ]

    if process_quickswap:
        requests.extend(
            [
                returns_manager.feed_db(
                    chain=chain, protocol=Protocol.QUICKSWAP, periods=periods
                )
            ]
        )

    await asyncio.gather(*requests)


async def test_get_data_from_Mongodb_v1():
    protocols = Protocol
    chains_protocols = [
        (chain, protocol)
        for protocol in protocols
        for chain in GAMMA_SUBGRAPH_URLS[protocol].keys()
    ]
    requests = list()

    #  managers
    allData_manager = db_allData_manager(mongo_url=MONGO_DB_URL)
    allRewards2_manager = db_allRewards2_manager(mongo_url=MONGO_DB_URL)
    returns_manager = db_returns_manager(mongo_url=MONGO_DB_URL)
    for chain, protocol in chains_protocols:
        feeReturns = await returns_manager.get_feeReturns(
            chain=chain, protocol=protocol, period=7
        )
        returns = await returns_manager.get_returns(chain=chain, protocol=protocol)
        allData = await allData_manager.get_data(chain=chain, protocol=protocol)
        Rewards2 = await allRewards2_manager.get_last_data(
            chain=chain, protocol=protocol
        )
        returns_average = await returns_manager.get_hypervisors_average(
            chain=chain, protocol=protocol
        )


async def test_get_data_from_Mongodb_v2():
    protocols = Protocol
    chains_protocols = [
        (chain, protocol)
        for protocol in protocols
        for chain in GAMMA_SUBGRAPH_URLS[protocol].keys()
    ]
    for chain, protocol in chains_protocols:
        # start time log
        _startime = dt.datetime.utcnow()
        impermanent = hypervisor.ImpermanentDivergence(
            protocol=protocol, chain=chain, days=1
        )
        impermanentDivergence_data = await impermanent.run(first=QueryType.DATABASE)
        print(
            "[{} {}]  took {} to complete Impermanent Divergence call".format(
                chain, protocol, get_timepassed_string(_startime)
            )
        )
        _startime = dt.datetime.utcnow()
        fee_returns = hypervisor.FeeReturns(protocol=protocol, chain=chain, days=1)
        fee_returns_data = await fee_returns.run(QueryType.DATABASE)
        print(
            "[{} {}]  took {} to complete FeeReturns call".format(
                chain, protocol, get_timepassed_string(_startime)
            )
        )
        _startime = dt.datetime.utcnow()
        hypervisor_returns = hypervisor.HypervisorsReturnsAllPeriods(
            protocol=protocol, chain=chain
        )
        allReturns_data = await hypervisor_returns.run(QueryType.DATABASE)
        print(
            "[{} {}]  took {} to complete Returns all Periods call".format(
                chain, protocol, get_timepassed_string(_startime)
            )
        )
        _startime = dt.datetime.utcnow()
        aggregate_stats = AggregateStats(protocol=protocol, chain=chain, response=None)
        aggregateStats_data = await aggregate_stats.run(QueryType.DATABASE)
        print(
            "[{} {}]  took {} to complete aggregateStats call".format(
                chain, protocol, get_timepassed_string(_startime)
            )
        )
        _startime = dt.datetime.utcnow()


def check_returns(data: dict, **kwargs):
    if not len(data) > 0:
        print(" Returns has no content")

    if not "datetime" in data.keys():
        print(" Returns has no datetime")

    for address, returns in data.items():
        if not set(["daily", "weekly", "monthly", "allTime"]).issubset(
            set(returns.keys())
        ):
            print(f" {address} return has is incomplete")
        for k, v in returns.items():
            if v == 0:
                print(f" {address} return is zero")


def get_timepassed_string(start_time: dt.datetime) -> str:
    _timelapse = dt.datetime.utcnow() - start_time
    _passed = _timelapse.total_seconds()
    if _passed < 60:
        _timelapse_unit = "seconds"
    elif _passed < 60 * 60:
        _timelapse_unit = "minutes"
        _passed /= 60
    elif _passed < 60 * 60 * 24:
        _timelapse_unit = "hours"
        _passed /= 60 * 60
    return "{:,.2f} {}".format(_passed, _timelapse_unit)


async def test_analytics():
    periods = [1, 7, 14, 30]

    static_manager = db_static_manager(mongo_url=MONGO_DB_URL)

    for chain in Chain:
        hypervisor_list = await static_manager.get_hypervisors_address_list(chain=chain)
        requests = [
            get_hype_data(
                chain=chain, hypervisor_address=hypervisor_address, period=period
            )
            for hypervisor_address in hypervisor_list
            for period in periods
        ]

        _startime = dt.datetime.utcnow()
        # execute feed
        results = await asyncio.gather(*requests)
        print(
            "[{}]  took {} to complete  call".format(
                chain, get_timepassed_string(_startime)
            )
        )


async def test_analytics_hype():
    periods = [14]
    chain = Chain.OPTIMISM
    hypervisor_list = ["0x431f6E577A431D9EE87a535fDE2dB830E352e33c".lower()]
    static_manager = db_static_manager(mongo_url=MONGO_DB_URL)

    requests = [
        get_hype_data(chain=chain, hypervisor_address=hypervisor_address, period=period)
        for hypervisor_address in hypervisor_list
        for period in periods
    ]

    _startime = dt.datetime.utcnow()
    # execute feed
    results = await asyncio.gather(*requests)
    print(
        "[{}]  took {} to complete aggregateStats call".format(
            chain, get_timepassed_string(_startime)
        )
    )


async def test_user_status(address: str, chains: list):
    for chain in chains:
        _startime = dt.datetime.utcnow()
        user_status = await users.get_user_analytic_data(
            chain=chain, address=address, response=None
        )
        print(
            "[{}]  took {} to complete user_status call".format(
                chain, get_timepassed_string(_startime)
            )
        )


# TESTING
if __name__ == "__main__":
    # start time log
    _startime = dt.datetime.utcnow()

    asyncio.run(test_analytics_hype())

    # end time log
    print(" took {} to complete the script".format(get_timepassed_string(_startime)))
