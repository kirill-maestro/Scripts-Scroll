from web3 import Web3
import os
import json
import time
from utils.transaction_utils import sign_transaction, send_raw_transaction, wait_for_transaction_finish, approve, get_amount_wei, get_randomized_amount, get_balance
from ScrollData import SCROLL_TOKENS, IZUMI_CONTRACT, ZERO_ADDRESS
from web3.middleware import geth_poa_middleware
from RPC import RPC_URL

# Loading the ABIs of the syncswap contracts
abi_path_swap = os.path.join(os.path.dirname(__file__), "abis/iZUMi/swap.json")
with open(abi_path_swap, "r") as file:
    IZUMI_SWAP_ABI = json.load(file)

abi_path_quoter = os.path.join(
    os.path.dirname(__file__), "abis/iZUMi/quoter.json")
with open(abi_path_quoter, "r") as file:
    IZUMI_QUOTER_ABI = json.load(file)

GAS_MULTIPLIER = 1.01


def iZUMi_swap(private_key, from_token, to_token, min_percentage, max_percentage, slippage=1):

    # Connect to the Ethereum network -> put your own RPC URL here
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # Add the middleware
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # Load the private key and get the account
    account = w3.eth.account.from_key(private_key)

    amount = get_randomized_amount(
        from_token, w3, account, min_percentage, max_percentage)

    balance_from_token = get_balance(from_token, w3, account)["balance"]
    balance_to_token = get_balance(to_token, w3, account)["balance"]

    # Set the default account
    w3.eth.default_account = account.address

    # Create the contract instance using the ABI and contract address
    contract_address_quoter = IZUMI_CONTRACT['quoter']
    contract_address_swap = IZUMI_CONTRACT['swap']

    contract_swap = w3.eth.contract(
        address=contract_address_swap, abi=IZUMI_SWAP_ABI)

    quoter_contract = w3.eth.contract(
        contract_address_quoter, abi=IZUMI_QUOTER_ABI)

    # Convert amount to wei format
    amount_wei = get_amount_wei(from_token, w3, account, amount)

    # Get the minimum amount out -> this is the minimum amount of the 'to_token' that will be received
    def get_min_amount_out(amount: int, path: bytes, slippage: float):
        try:
            min_amount_out = quoter_contract.functions.swapAmount(
                amount,
                path
            ).call()
        except Exception as error:
            print(f"❌ get_min_amount_out failed [{account.address}] {error}")
            return

        return int(min_amount_out[0] - (min_amount_out[0] / 100 * slippage))

    def fee_2_hex(fee: int):
        n0 = fee % 16
        n1 = (fee // 16) % 16
        n2 = (fee // 256) % 16
        n3 = (fee // 4096) % 16
        n4 = 0
        n5 = 0
        return '0x' + num_2_hex(n5) + num_2_hex(n4) + num_2_hex(n3) + num_2_hex(n2) + num_2_hex(n1) + num_2_hex(n0)

    def num_2_hex(num: int):

        if num < 10:
            return str(num)
        strs = 'ABCDEF'
        return strs[num - 10]

    def get_path(token_chain: list, fee_chain: list):
        hex_str = token_chain[0]
        for i in range(len(fee_chain)):
            hex_str += fee_2_hex(fee_chain[i])
            hex_str += token_chain[i+1]

        return hex_str

    print(
        f"🏛️ [{account.address}] current balance [{balance_from_token}] [{from_token}] | [{balance_to_token}] [{to_token}]")
    print(
        f"🛫 [{account.address}] starting to swap [{amount}] [{from_token}] to [{to_token}]")

    def swap():
        try:
            deadline = int(time.time()) + 1000000

            if (from_token == 'ETH' and to_token == 'USDC') or (from_token == 'USDC' and to_token == 'ETH'):
                fee = 400  # 0.2%
                token_chain = [
                    Web3.to_checksum_address(SCROLL_TOKENS[from_token]),
                    Web3.to_checksum_address(SCROLL_TOKENS['USDT']),
                    Web3.to_checksum_address(SCROLL_TOKENS[to_token])
                ]
                fee_chain = [fee, fee]
            if (from_token == 'ETH' and to_token == 'USDT') or (from_token == 'USDT' and to_token == 'ETH'):
                fee = 500  # 0.05%

                token_chain = [
                    Web3.to_checksum_address(SCROLL_TOKENS[from_token]),
                    Web3.to_checksum_address(SCROLL_TOKENS[to_token])
                ]

                fee_chain = [fee]

            if (from_token == 'ETH' and to_token == 'WETH') or (from_token == 'WETH' and to_token == 'ETH'):
                fee = 0  # 0.0%

                token_chain = [
                    Web3.to_checksum_address(SCROLL_TOKENS[from_token]),
                    Web3.to_checksum_address(SCROLL_TOKENS[to_token])
                ]

                fee_chain = [fee]

            # So basically the idea is the following: there are no router functions or similar in ABIs that gives us the path directly, so we need to create it manually.
            # The front end shows that the most favorable path for ETH to USDC is ETH -> USDT -> USDC path (it might change).
            # We need to put the fees in hex inbetween the token addresses: like ETH_address + fee in hex + USDT_address + fee in hex + USDC_address
            path = get_path(token_chain, fee_chain)

            # Removing “0x” part
            path = path.replace("0x", "")

            if from_token != 'ETH':
                approve(amount_wei, Web3.to_checksum_address(
                    SCROLL_TOKENS[from_token]), Web3.to_checksum_address(IZUMI_CONTRACT["swap"]), account, w3)

            min_amount_out = get_min_amount_out(
                amount_wei, Web3.to_bytes(hexstr=path), slippage)

            args = [[
                Web3.to_bytes(hexstr=path),
                account.address if from_token == 'ETH' else Web3.to_checksum_address(
                    ZERO_ADDRESS),
                amount_wei,
                min_amount_out,
                deadline,
            ]]
            encode_data = contract_swap.encodeABI(
                fn_name='swapAmount', args=args)

            if from_token == 'ETH':
                call_args = [
                    encode_data,
                    # refundETH 4bytes method-id
                    Web3.to_bytes(hexstr='0x12210e8a')
                ]
            else:
                call_args = [
                    encode_data,
                    contract_swap.encodeABI(fn_name='unwrapWETH9', args=[
                        0,
                        account.address
                    ])
                ]

            contract_transaction = contract_swap.functions.multicall(call_args).build_transaction({
                'chainId': w3.eth.chain_id,
                'value': amount_wei if from_token == 'ETH' else 0,
                'nonce': w3.eth.get_transaction_count(account.address),
                'from': account.address,
                'gasPrice': w3.eth.gas_price,
            })

            try:
                signed_transaction = sign_transaction(
                    contract_transaction, w3, private_key, GAS_MULTIPLIER)
            except Exception as exception:
                print(f"sign_transaction failed | {signed_transaction}")

            try:
                transaction_hash = send_raw_transaction(signed_transaction, w3)
            except Exception as exception:
                print(f"send_raw_transaction failed | {exception}")

            wait_for_transaction_finish(transaction_hash.hex(), account, w3)
            print(
                f"🏁 [{account.address}] swaped from amount [{amount}] [{from_token}] to [{to_token}]")

            new_balance_from_token = get_balance(
                from_token, w3, account)["balance"]
            new_balance_to_token = get_balance(
                to_token, w3, account)["balance"]
            print(
                f"🏛️ [{account.address}] new balance [{new_balance_from_token}] [{from_token}] | [{new_balance_to_token}] [{to_token}]")
            print(f"📊 [{account.address}] balance change [{new_balance_from_token - balance_from_token}] [{from_token}] | [{new_balance_to_token - balance_to_token}] [{to_token}]")

        except Exception as error:
            print(f"❌ iZUMi swap failed [{account.address}] {error}")
    swap()


def main():
    # SETTINGS START HERE:
    min_percentage = 90  # From how much % of your from_token balance do you want to swap?
    max_percentage = 100  # To how much % of your from_token balance do you want to swap? At the end the get_randomized_amount function will return a random amount between min_percentage and max_percentage
    from_token = 'USDT'  # ETH, WETH, WBTC, USDT, USDC, BUSD, MATIC available
    to_token = 'ETH'  # ETH, WETH, WBTC, USDT, USDC, BUSD, MATIC available
    slippage = 5  # The slippage tolerance in percentage
    # SETTINGS END HERE

    with open('keys.txt', 'r') as file:
        for private_key in file:
            private_key = private_key.strip()
            iZUMi_swap(private_key, from_token, to_token,
                       min_percentage, max_percentage, slippage)


main()
