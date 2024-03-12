from web3 import Web3
import os
import json
import time
from eth_abi import abi
from utils.transaction_utils import sign_transaction, send_raw_transaction, wait_for_transaction_finish, approve, get_amount_wei, get_token_price_usd, get_balance, get_randomized_amount
from ScrollData import SCROLL_TOKENS, ZERO_ADDRESS, AMBIENT_CONTRACT
from RPC import RPC_URL

# Loading the ABIs of the syncswap contracts
abi_swap = os.path.join(os.path.dirname(
    __file__), "abis/ambient/swap.json")
with open(abi_swap, "r") as file:
    AMBIENT_SWAP_ABI = json.load(file)

GAS_MULTIPLIER = 1.01


def ambient(private_key, from_token, to_token, min_percentage, max_percentage, slippage=1):
    # Connect to the Ethereum network -> put your own RPC URL here
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # Load the private key and get the account
    account = w3.eth.account.from_key(private_key)

    # Create the contract instance using the ABI and contract address
    contract_address = AMBIENT_CONTRACT['swap']

    contract_swap = w3.eth.contract(
        address=contract_address, abi=AMBIENT_SWAP_ABI)

    amount = get_randomized_amount(
        from_token, w3, account, min_percentage, max_percentage)

    balance_from_token = get_balance(from_token, w3, account)["balance"]
    balance_to_token = get_balance(to_token, w3, account)["balance"]

    # Convert amount to wei format (depending on the token decimal, e.g. USDC has 6 decimals and ETH has 18 decimals)
    amount_wei = get_amount_wei(from_token, w3, account, amount)

    # Get the gas price
    gas_price = w3.eth.gas_price

    # Construct the transaction
    transaction = {
        'chainId': w3.eth.chain_id,
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gasPrice': gas_price,
    }

    def get_min_amount_out(from_token, to_token, from_token_amount):

        amount_in_usd = (get_token_price_usd(from_token)) * from_token_amount
        min_amount_out = (amount_in_usd / get_token_price_usd(to_token))

        min_amount_out_in_wei = get_amount_wei(
            to_token, w3, account, min_amount_out)

        return int(min_amount_out_in_wei - (min_amount_out_in_wei / 100 * slippage))

    print(f"🏛️ [{account.address}] current balance [{balance_from_token}] [{from_token}] | [{balance_to_token}] [{to_token}]")
    print(
        f"🛫 [{account.address}] starting to swap [{amount}] [{from_token}] to [{to_token}]")

    def swap():
        max_sqrt_price = 21267430153580247136652501917186561137
        min_sqrt_price = 65537
        pool_idx = 420
        reserve_flags = 0
        tip = 0

        min_amount_out = get_min_amount_out(from_token, to_token, amount)

        if from_token != 'ETH':
            approve(
                amount_wei, SCROLL_TOKENS[from_token], contract_address, account, w3)
            transaction.update({"value": 0})
            transaction.update(
                {"nonce": w3.eth.get_transaction_count(account.address)})
        else:
            transaction.update({"value": amount_wei})

        encode_data = abi.encode(
            ['address', 'address', 'uint16', 'bool', 'bool', 'uint256', 'uint8', 'uint256', 'uint256', 'uint8'], [
                ZERO_ADDRESS,
                SCROLL_TOKENS[to_token] if from_token == 'ETH' else SCROLL_TOKENS[from_token],
                pool_idx,
                True if from_token == 'ETH' else False,
                True if from_token == 'ETH' else False,
                amount_wei,
                tip,
                max_sqrt_price if from_token == 'ETH' else min_sqrt_price,
                min_amount_out,
                reserve_flags
            ]
        )

        contract_transaction = contract_swap.functions.userCmd(
            1,
            encode_data
        ).build_transaction(transaction)

        signed_transaction = sign_transaction(
            contract_transaction, w3, private_key, GAS_MULTIPLIER)

        transaction_hash = send_raw_transaction(signed_transaction, w3)

        wait_for_transaction_finish(transaction_hash.hex(), account, w3)
        print(
            f"🏁 [{account.address}] swaped from amount [{amount}] [{from_token}] to [{to_token}]")

        new_balance_from_token = get_balance(
            from_token, w3, account)["balance"]
        new_balance_to_token = get_balance(to_token, w3, account)["balance"]
        print(f"🏛️ [{account.address}] new balance [{new_balance_from_token}] [{from_token}] | [{new_balance_to_token}] [{to_token}]")
        print(f"📊 [{account.address}] balance change [{new_balance_from_token - balance_from_token}] [{from_token}] | [{new_balance_to_token - balance_to_token}] [{to_token}]")

    swap()


def main():
    # SETTINGS START HERE:
    min_percentage = 100  # From how much % of your from_token balance do you want to swap?
    max_percentage = 100  # To how much % of your from_token balance do you want to swap? At the end the get_randomized_amount function will return a random amount between min_percentage and max_percentage
    from_token = 'USDT'  # ETH, WETH, WBTC, USDT, USDC, BUSD, MATIC available
    to_token = 'ETH'  # ETH, WETH, WBTC, USDT, USDC, BUSD, MATIC available
    slippage = 5  # The slippage tolerance in percentage
    # SETTINGS END HERE

    with open('keys.txt', 'r') as file:
        for private_key in file:
            private_key = private_key.strip()
            ambient(private_key, from_token, to_token,
                    min_percentage, max_percentage, slippage)


main()
