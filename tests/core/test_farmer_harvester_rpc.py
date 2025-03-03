# flake8: noqa: E501
import logging
from secrets import token_bytes

import pytest
from blspy import AugSchemeMPL
from melatipos import DiskPlotter

from melati.consensus.coinbase import create_puzzlehash_for_pk
from melati.plotting.plot_tools import stream_plot_info_ph, stream_plot_info_pk
from melati.protocols import farmer_protocol
from melati.rpc.farmer_rpc_api import FarmerRpcApi
from melati.rpc.farmer_rpc_client import FarmerRpcClient
from melati.rpc.harvester_rpc_api import HarvesterRpcApi
from melati.rpc.harvester_rpc_client import HarvesterRpcClient
from melati.rpc.rpc_server import start_rpc_server
from melati.types.blockchain_format.sized_bytes import bytes32
from melati.util.bech32m import decode_puzzle_hash, encode_puzzle_hash
from tests.block_tools import get_plot_dir
from melati.util.byte_types import hexstr_to_bytes
from melati.util.config import load_config, save_config
from melati.util.hash import std_hash
from melati.util.ints import uint8, uint16, uint32, uint64
from melati.wallet.derive_keys import master_sk_to_wallet_sk, master_sk_to_pooling_authentication_sk
from tests.setup_nodes import bt, self_hostname, setup_farmer_harvester, test_constants
from tests.time_out_assert import time_out_assert

log = logging.getLogger(__name__)


class TestRpc:
    @pytest.fixture(scope="function")
    async def simulation(self):
        async for _ in setup_farmer_harvester(test_constants):
            yield _

    @pytest.mark.asyncio
    async def test1(self, simulation):
        test_rpc_port = uint16(21522)
        test_rpc_port_2 = uint16(21523)
        harvester, farmer_api = simulation

        def stop_node_cb():
            pass

        def stop_node_cb_2():
            pass

        config = bt.config
        hostname = config["self_hostname"]
        daemon_port = config["daemon_port"]

        farmer_rpc_api = FarmerRpcApi(farmer_api.farmer)
        harvester_rpc_api = HarvesterRpcApi(harvester)

        rpc_cleanup = await start_rpc_server(
            farmer_rpc_api,
            hostname,
            daemon_port,
            test_rpc_port,
            stop_node_cb,
            bt.root_path,
            config,
            connect_to_daemon=False,
        )
        rpc_cleanup_2 = await start_rpc_server(
            harvester_rpc_api,
            hostname,
            daemon_port,
            test_rpc_port_2,
            stop_node_cb_2,
            bt.root_path,
            config,
            connect_to_daemon=False,
        )

        try:
            client = await FarmerRpcClient.create(self_hostname, test_rpc_port, bt.root_path, config)
            client_2 = await HarvesterRpcClient.create(self_hostname, test_rpc_port_2, bt.root_path, config)

            async def have_connections():
                return len(await client.get_connections()) > 0

            await time_out_assert(15, have_connections, True)

            assert (await client.get_signage_point(std_hash(b"2"))) is None
            assert len(await client.get_signage_points()) == 0

            async def have_signage_points():
                return len(await client.get_signage_points()) > 0

            sp = farmer_protocol.NewSignagePoint(
                std_hash(b"1"), std_hash(b"2"), std_hash(b"3"), uint64(1), uint64(1000000), uint8(2)
            )
            await farmer_api.new_signage_point(sp)

            await time_out_assert(5, have_signage_points, True)
            assert (await client.get_signage_point(std_hash(b"2"))) is not None

            async def have_plots():
                return len((await client_2.get_plots())["plots"]) > 0

            await time_out_assert(5, have_plots, True)

            res = await client_2.get_plots()
            num_plots = len(res["plots"])
            assert num_plots > 0
            plot_dir = get_plot_dir() / "subdir"
            plot_dir.mkdir(parents=True, exist_ok=True)

            plot_dir_sub = get_plot_dir() / "subdir" / "subsubdir"
            plot_dir_sub.mkdir(parents=True, exist_ok=True)

            plotter = DiskPlotter()
            filename = "test_farmer_harvester_rpc_plot.plot"
            filename_2 = "test_farmer_harvester_rpc_plot2.plot"
            plotter.create_plot_disk(
                str(plot_dir),
                str(plot_dir),
                str(plot_dir),
                filename,
                18,
                stream_plot_info_pk(bt.pool_pk, bt.farmer_pk, AugSchemeMPL.key_gen(bytes([4] * 32))),
                token_bytes(32),
                128,
                0,
                2000,
                0,
                False,
            )

            # Making a plot with a puzzle hash encoded into it instead of pk
            plot_id_2 = token_bytes(32)
            plotter.create_plot_disk(
                str(plot_dir),
                str(plot_dir),
                str(plot_dir),
                filename_2,
                18,
                stream_plot_info_ph(std_hash(b"random ph"), bt.farmer_pk, AugSchemeMPL.key_gen(bytes([5] * 32))),
                plot_id_2,
                128,
                0,
                2000,
                0,
                False,
            )

            # Making the same plot, in a different dir. This should not be farmed
            plotter.create_plot_disk(
                str(plot_dir_sub),
                str(plot_dir_sub),
                str(plot_dir_sub),
                filename_2,
                18,
                stream_plot_info_ph(std_hash(b"random ph"), bt.farmer_pk, AugSchemeMPL.key_gen(bytes([5] * 32))),
                plot_id_2,
                128,
                0,
                2000,
                0,
                False,
            )

            res_2 = await client_2.get_plots()
            assert len(res_2["plots"]) == num_plots

            # Test farmer get_harvesters
            await farmer_rpc_api.service.update_cached_harvesters()
            farmer_res = await client.get_harvesters()
            assert len(list(farmer_res["harvesters"])) == 1
            assert len(list(farmer_res["harvesters"][0]["plots"])) == num_plots

            assert len(await client_2.get_plot_directories()) == 1

            await client_2.add_plot_directory(str(plot_dir))
            await client_2.add_plot_directory(str(plot_dir_sub))

            assert len(await client_2.get_plot_directories()) == 3

            res_2 = await client_2.get_plots()
            assert len(res_2["plots"]) == num_plots + 2

            await client_2.delete_plot(str(plot_dir / filename))
            await client_2.delete_plot(str(plot_dir / filename_2))
            await client_2.refresh_plots()
            res_3 = await client_2.get_plots()

            assert len(res_3["plots"]) == num_plots + 1

            await client_2.remove_plot_directory(str(plot_dir))
            assert len(await client_2.get_plot_directories()) == 2

            targets_1 = await client.get_reward_targets(False)
            assert "have_pool_sk" not in targets_1
            assert "have_farmer_sk" not in targets_1
            targets_2 = await client.get_reward_targets(True)
            assert targets_2["have_pool_sk"] and targets_2["have_farmer_sk"]

            new_ph: bytes32 = create_puzzlehash_for_pk(master_sk_to_wallet_sk(bt.farmer_master_sk, uint32(10)).get_g1())
            new_ph_2: bytes32 = create_puzzlehash_for_pk(
                master_sk_to_wallet_sk(bt.pool_master_sk, uint32(472)).get_g1()
            )

            await client.set_reward_targets(encode_puzzle_hash(new_ph, "xch"), encode_puzzle_hash(new_ph_2, "xch"))
            targets_3 = await client.get_reward_targets(True)
            assert decode_puzzle_hash(targets_3["farmer_target"]) == new_ph
            assert decode_puzzle_hash(targets_3["pool_target"]) == new_ph_2
            assert targets_3["have_pool_sk"] and targets_3["have_farmer_sk"]

            new_ph_3: bytes32 = create_puzzlehash_for_pk(
                master_sk_to_wallet_sk(bt.pool_master_sk, uint32(1888)).get_g1()
            )
            await client.set_reward_targets(None, encode_puzzle_hash(new_ph_3, "xch"))
            targets_4 = await client.get_reward_targets(True)
            assert decode_puzzle_hash(targets_4["farmer_target"]) == new_ph
            assert decode_puzzle_hash(targets_4["pool_target"]) == new_ph_3
            assert not targets_4["have_pool_sk"] and targets_3["have_farmer_sk"]

            root_path = farmer_api.farmer._root_path
            config = load_config(root_path, "config.yaml")
            assert config["farmer"]["xch_target_address"] == encode_puzzle_hash(new_ph, "xch")
            assert config["pool"]["xch_target_address"] == encode_puzzle_hash(new_ph_3, "xch")

            new_ph_3_encoded = encode_puzzle_hash(new_ph_3, "xch")
            added_char = new_ph_3_encoded + "a"
            with pytest.raises(ValueError):
                await client.set_reward_targets(None, added_char)

            replaced_char = new_ph_3_encoded[0:-1] + "a"
            with pytest.raises(ValueError):
                await client.set_reward_targets(None, replaced_char)

            assert len((await client.get_pool_state())["pool_state"]) == 0
            all_sks = farmer_api.farmer.keychain.get_all_private_keys()
            auth_sk = master_sk_to_pooling_authentication_sk(all_sks[0][0], 2, 1)
            pool_list = [
                {
                    "launcher_id": "ae4ef3b9bfe68949691281a015a9c16630fc8f66d48c19ca548fb80768791afa",
                    "authentication_public_key": bytes(auth_sk.get_g1()).hex(),
                    "owner_public_key": "84c3fcf9d5581c1ddc702cb0f3b4a06043303b334dd993ab42b2c320ebfa98e5ce558448615b3f69638ba92cf7f43da5",
                    "payout_instructions": "c2b08e41d766da4116e388357ed957d04ad754623a915f3fd65188a8746cf3e8",
                    "pool_url": "localhost",
                    "p2_singleton_puzzle_hash": "16e4bac26558d315cded63d4c5860e98deb447cc59146dd4de06ce7394b14f17",
                    "target_puzzle_hash": "344587cf06a39db471d2cc027504e8688a0a67cce961253500c956c73603fd58",
                }
            ]
            config["pool"]["pool_list"] = pool_list
            save_config(root_path, "config.yaml", config)
            await farmer_api.farmer.update_pool_state()

            pool_state = (await client.get_pool_state())["pool_state"]
            assert len(pool_state) == 1
            assert (
                pool_state[0]["pool_config"]["payout_instructions"]
                == "c2b08e41d766da4116e388357ed957d04ad754623a915f3fd65188a8746cf3e8"
            )
            await client.set_payout_instructions(hexstr_to_bytes(pool_state[0]["pool_config"]["launcher_id"]), "1234vy")

            pool_state = (await client.get_pool_state())["pool_state"]
            assert pool_state[0]["pool_config"]["payout_instructions"] == "1234vy"

        finally:
            # Checks that the RPC manages to stop the node
            client.close()
            client_2.close()
            await client.await_closed()
            await client_2.await_closed()
            await rpc_cleanup()
            await rpc_cleanup_2()
