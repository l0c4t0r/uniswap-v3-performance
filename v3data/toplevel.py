import numpy as np
from datetime import timedelta
from pandas import DataFrame

from v3data import VisorClient
from v3data.visr import VisrData
from v3data.utils import timestamp_ago


class TopLevelData:
    """Top level stats"""

    def __init__(self):
        self.visor_client = VisorClient()

    def get_factory_data(self):
        """Get factory aggregated data for all factories"""
        query = """
        {
            uniswapV3HypervisorFactories(
                first: 1000
            ){
                id
                grossFeesClaimedUSD
                tvlUSD
            }
        }
        """
        return self.visor_client.query(query)['data']['uniswapV3HypervisorFactories']

    def get_pool_data(self):
        query = """
        {
            uniswapV3Pools(
                first: 1000
            ){
                id
            }
        }
        """
        return self.visor_client.query(query)['data']['uniswapV3Pools']

    def get_recent_rebalance_data(self, hours=24):
        query = """
        query rebalances($timestamp_start: Int!){
            uniswapV3Rebalances(
                first: 1000
                where: {
                    timestamp_gte: $timestamp_start
                }
            ) {
                grossFeesUSD
                protocolFeesUSD
                netFeesUSD
            }
        }
        """
        timestamp_start = timestamp_ago(timedelta(hours=hours))
        variables = {"timestamp_start": timestamp_start}
        return self.visor_client.query(query, variables)['data']['uniswapV3Rebalances']

    def all_stats(self):
        """
        Aggregate TVL and fees generated stats from all factories
        Should add entity to subgraph to track top level stats
        """
        data = self.get_factory_data()
        pool_data = self.get_pool_data()
        return {
            "pool_count": len(pool_data),
            "tvl": sum([float(factory['tvlUSD']) for factory in data]),
            "fees_claimed": sum([float(factory['grossFeesClaimedUSD']) for factory in data])
        }

    def recent_fees(self, hours=24):
        visr = VisrData()
        visr_price = visr.price_usd()
        data = self.get_recent_rebalance_data(hours)
        df_fees = DataFrame(data, dtype=np.float64)

        df_fees['grossFeesVISR'] = df_fees.grossFeesUSD / visr_price
        df_fees['protocolFeesVISR'] = df_fees.protocolFeesUSD / visr_price
        df_fees['netFeesVISR'] = df_fees.netFeesUSD / visr_price

        return df_fees.sum().to_dict()