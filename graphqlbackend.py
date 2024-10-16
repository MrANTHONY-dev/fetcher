import json
import urllib.request
from PIL import Image
import requests
from graphene import ObjectType, List, String, JSONString
from web3 import Web3

# Initialize Web3
w3 = Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))

# Simplified ABI for standard NFT functions
simplified_abi = [
    {
        'inputs': [{'internalType': 'address', 'name': 'owner', 'type': 'address'}],
        'name': 'balanceOf',
        'outputs': [{'internalType': 'uint256', 'name': '', 'type': 'uint256'}],
        'stateMutability': 'view', 'type': 'function', 'constant': True
    },
    {
        'inputs': [],
        'name': 'name',
        'outputs': [{'internalType': 'string', 'name': '', 'type': 'string'}],
        'stateMutability': 'view', 'type': 'function', 'constant': True
    },
    {
        'inputs': [{'internalType': 'uint256', 'name': 'tokenId', 'type': 'uint256'}],
        'name': 'ownerOf',
        'outputs': [{'internalType': 'address', 'name': '', 'type': 'address'}],
        'stateMutability': 'view', 'type': 'function', 'constant': True
    },
    {
        'inputs': [{'internalType': 'uint256', 'name': 'tokenId', 'type': 'uint256'}],
        'name': 'tokenURI',
        'outputs': [{'internalType': 'string', 'name': '', 'type': 'string'}],
        'stateMutability': 'view', 'type': 'function', 'constant': True
    },
    {
        'inputs': [],
        'name': 'symbol',
        'outputs': [{'internalType': 'string', 'name': '', 'type': 'string'}],
        'stateMutability': 'view', 'type': 'function', 'constant': True
    },
    {
        'inputs': [],
        'name': 'totalSupply',
        'outputs': [{'internalType': 'uint256', 'name': '', 'type': 'uint256'}],
        'stateMutability': 'view', 'type': 'function', 'constant': True
    },
]

def fetch_image_data(image_url):
    """Fetches image data and returns the width and height."""
    try:
        with urllib.request.urlopen(image_url, timeout=0.5) as response:
            image = Image.open(response)
            width, height = image.size
            return int(width / 1000) or 1, int(height / 1000) or 1  # Avoid zero dimensions
    except Exception as e:
        print(f"Error fetching image data: {e}")
        return None, None

def get_uri(contract_address, token_id, owner_address):
    """Fetches NFT metadata and image dimensions for a given contract and token ID."""
    image_links = []
    total_uri = []
    
    for ca, ti in zip(contract_address, token_id):
        ck_contract = w3.eth.contract(address=w3.toChecksumAddress(ca), abi=simplified_abi)
        try:
            name = ck_contract.functions.name().call()
            symbol = ck_contract.functions.symbol().call()
            uri = ck_contract.functions.tokenURI(ti).call()
            owner = ck_contract.functions.ownerOf(ti).call()

            if owner.lower() == owner_address.lower():
                x = requests.get(uri).json()
                ipfsurl = 'https://ipfs.io/ipfs/'
                imageurl = x.get("image")
                
                if 'ipfs://' in imageurl:
                    imageurl = ipfsurl + imageurl.split("ipfs://")[1]

                width, height = fetch_image_data(imageurl)
                if width is not None and height is not None:
                    image_links.append([imageurl, width, height])
                    total_uri.append(x)
        except Exception as e:
            print(f"Error fetching data for {ca}, token ID {ti}: {e}")
    
    return total_uri, image_links

def get_address(address):
    """Fetches NFT transactions for a given Ethereum address."""
    with open('key.json') as key_file:
        key = json.load(key_file)['key']

    api_url = f"https://api.etherscan.io/api?module=account&action=tokennfttx&address={address}&startblock=0&endblock=999999999&sort=asc&apikey={key}"
    response = requests.get(api_url)
    all_transactions = response.json().get("result", [])

    contracts, ids = zip(*[(t.get("contractAddress"), int(t.get("tokenID"))) for t in all_transactions if t.get("to") == address])
    return list(contracts), list(ids)

class NFTS(ObjectType):
    uri = List(JSONString)
    address = String()
    images = List(String)
    name = String()

class Query(ObjectType):
    vp = List(NFTS, wa=String())
    random = List(NFTS)

    def resolve_vp(self, info, wa):
        contract_address, token_id = get_address(wa)
        uri, image_links = get_uri(contract_address, token_id, wa)
        return [{"uri": uri, "address": wa, "images": image_links, "owner": "You"}]

    def resolve_random(self, info):
        address, owner = fetch_random()
        contract_address, token_id = get_address(address)
        uri, image_links = get_uri(contract_address, token_id, address)
        return [{"uri": uri, "address": address, "images": image_links, "name": owner}]

def fetch_random():
    """Fetches a random address from a CSV file."""
    import pandas as pd
    from random import randrange
    df = pd.read_csv('data.csv')
    row = df.iloc[randrange(len(df))]
    return row[1], row[0]  # Assuming the first column is the owner and second is the address

if __name__ == "__main__":
    # Example usage
    address = '0xa679c6154b8d4619af9f83f0bf9a13a680e01ecf'
    contract_address, token_id = get_address(address)
    uri, image_links = get_uri(contract_address, token_id, address)
    print({"uri": uri, "address": address, "images": image_links})
