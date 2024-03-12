from web3 import Web3
import os
import json
import random
from utils.transaction_utils import sign_transaction, send_raw_transaction, wait_for_transaction_finish, get_balance
from ScrollData import DMAIL_CONTRACT
from RPC import RPC_URL

# Loading the ABIs of the syncswap contracts
abi_path_dmail = os.path.join(
    os.path.dirname(__file__), "abis/dmail/dmail.json")
with open(abi_path_dmail, "r") as file:
    DMAIL_ABI = json.load(file)

GAS_MULTIPLIER = 1.01


def dmail(private_key, random_receiver):
    # Connect to the Ethereum network -> put your own RPC URL here
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # Load the private key and get the account
    account = w3.eth.account.from_key(private_key)

    # Set the default account
    w3.eth.default_account = account.address

    balance_ETH = get_balance('ETH', w3, account)["balance"]

    # Create the contract instance using the ABI and contract address
    contract_address = Web3.to_checksum_address(DMAIL_CONTRACT['dmail'])

    contract_send_dmail = w3.eth.contract(
        address=contract_address, abi=DMAIL_ABI)

    # Get the gas price
    gas_price = w3.eth.gas_price

    # Construct the transaction
    transaction = {
        'chainId': w3.eth.chain_id,
        'from': account.address,
        'to': Web3.to_checksum_address(DMAIL_CONTRACT['dmail']),
        'nonce': w3.eth.get_transaction_count(account.address),
        'gasPrice': gas_price,
    }

    def get_random_email():
        domain_list = ["@gmail.com", "@dmail.ai"]

        domain_address = "".join(random.sample(
            [chr(i) for i in range(97, 123)], random.randint(7, 15)))

        return domain_address + random.choice(domain_list)

    print(
        f"🏛️ [{account.address}] current balance [{balance_ETH}] ETH")
    print(
        f"🛫 [{account.address}] starting to send dmail")

    def send_mail(random_receiver: bool):

        email_address = get_random_email(
        ) if random_receiver else f"{account.address}@dmail.ai"

        data = contract_send_dmail.encodeABI(
            "send_mail", args=(email_address, email_address))

        transaction.update({"data": data})

        signed_transcation = sign_transaction(
            transaction, w3, private_key, GAS_MULTIPLIER)

        transaction_hash = send_raw_transaction(signed_transcation, w3)

        wait_for_transaction_finish(transaction_hash.hex(), account, w3)
        print(f"🏁 [{account.address}] Email sent")
        new_balance_ETH = get_balance('ETH', w3, account)["balance"]
        print(
            f"🏛️ [{account.address}] new balance [{new_balance_ETH}] ETH")
        print(
            f"📊 [{account.address}] balance change [{new_balance_ETH - balance_ETH}] ETH")

    send_mail(random_receiver)


def main():
    # SETTINGS START HERE:
    random_receiver = True  # do you want to send to your own email or to a random email?
    # SETTINGS END HERE

    with open('keys.txt', 'r') as file:
        for private_key in file:
            private_key = private_key.strip()
            dmail(private_key, random_receiver)


main()
