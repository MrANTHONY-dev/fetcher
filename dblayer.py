import os
import logging
import traceback
from pymongo import MongoClient
from PIL import Image
import requests
from urllib.request import Request, urlopen
from web3 import Web3
from multiprocessing.dummy import Pool as ThreadPool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'your_mongodb_connection_string')
INFURA_URL = os.getenv('INFURA_URL', 'https://mainnet.infura.io/v3/YOUR_INFURA_KEY')
client = MongoClient(MONGODB_URI)

# Web3 setup
w3 = Web3(Web3.HTTPProvider(INFURA_URL))
simplified_abi = [...]  # Define your ABI here

def fetch_nft_data(ca: str, ti: int, owner_address: str, land: bool) -> tuple:
    try:
        contract = w3.eth.contract(address=w3.toChecksumAddress(ca), abi=simplified_abi)
        try:
            uri = contract.functions.tokenURI(ti).call()
        except Exception:
            uri = contract.functions.uri(ti).call()

        # Check owner
        owner = contract.functions.ownerOf(ti).call()
        if owner.lower() != owner_address.lower() and owner_address != "":
            return None, None
        
        # Process URI
        ipfsurl = 'https://ipfs.io/ipfs/'
        if 'ipfs://' in uri:
            uri = ipfsurl + uri.split("ipfs://")[1]

        headers = {'User-Agent': 'Mozilla/5.0'}
        x = requests.get(uri, headers=headers)
        xjson = x.json()

        imageurl = xjson.get("image")
        if 'ipfs://' in imageurl:
            imageurl = ipfsurl + imageurl.split("ipfs://")[1]

        # Image processing
        req = Request(imageurl)
        req.add_header('User-Agent', headers.get('User-Agent'))
        image = Image.open(urlopen(req, timeout=5))
        width, height = image.size

        xjson["height"] = height
        xjson["width"] = width
        xjson["address"] = ca
        xjson["token_id"] = ti

        return xjson, [imageurl, width, height]
    
    except Exception as e:
        logger.error(f"Error fetching NFT data for {ca}, token ID {ti}: {e}")
        logger.debug(traceback.format_exc())
        return None, None

def threadfetch(inp: list) -> list:
    ca, ti, owner_address, land = inp
    return fetch_nft_data(ca, int(ti), owner_address, land)

def create_object(client, object_name, collection_name, info, key):
    db = client[object_name]
    db[collection_name].update(key, info, upsert=True)

def insert_object(client, object_name, collection_name, info):
    db = client[object_name]
    db[collection_name].insert_one(info)

def find_one(collection, table, address, token_id):
    db = client[collection]
    return db[table].find_one({"address": address, "token_id": str(token_id)})

def find_nft(address, token_id):
    return find_one('NFTGallery', 'nft', address, token_id)

def get_user_gallery(user_address):
    gallery = find_one('NFTGallery', 'users', user_address).get('gallery', [])
    uriarray = []
    imagearray = []

    for g in gallery:
        address = g.get("address")
        token_id = g.get("token_id")
        nft = find_nft(address, token_id)
        if nft is None:
            nft = threadfetch([address, token_id, "", False])
        else:
            nft = format_nft(nft)
        if nft is not None:
            uriarray.append(nft[0])
            imagearray.append(nft[1])
    return uriarray, imagearray

def format_nft(nft):
    return [nft.get("uri"), [nft.get('image'), nft.get("uri").get('height'), nft.get("uri").get('width')]]

def get_latest_opensea(marker=0):
    api_url = f"https://api.opensea.io/api/v1/events?only_opensea=false&offset={marker}&limit=2000"
    try:
        x = requests.get(api_url)
        jsun = x.json()
        return [(e["asset"]["asset_contract"]["address"], e["asset"]["token_id"]) for e in jsun.get("asset_events", []) if e["asset"]]
    except Exception as e:
        logger.error(f"Error fetching latest OpenSea events: {e}")
        return [], []

def job_function():
    collection = 'NFTGallery'
    table = 'latest'
    db = client[collection]
    
    # Get latest from OpenSea
    results_contracts = []
    results_tokens = []
    marker = 0
    while len(results_contracts) < 200:
        contracts, tokens = get_latest_opensea(marker)
        if not contracts:
            break
        uri, image_links = get_uri(contracts, tokens, "", land=False)
        results_contracts.extend(uri)
        results_tokens.extend(image_links)
        marker += 2000

    # Put into database
    insert_input = [{'token_id': rc["token_id"], 'address': rc["address"], 'uri': rc, 'image': rc.get("image"), 'points': 0} for rc in results_contracts]
    if insert_input:
        db[table].delete_many({})
        db[table].insert_many(insert_input)
    else:
        logger.info("No new NFTs to insert.")

if __name__ == "__main__":
    job_function()
