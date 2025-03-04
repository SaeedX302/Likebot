from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import os
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError

app = Flask(__name__)

# ✅ Load tokens from environment variables (Vercel-friendly)
def load_tokens(server_name):
    try:
        token_data = os.getenv(f"TOKEN_{server_name}")
        if token_data:
            return json.loads(token_data)
        else:
            raise Exception(f"Missing token for {server_name}")
    except Exception as e:
        app.logger.error(f"Error loading tokens: {e}")
        return None

# ✅ Encrypt message for requests
def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Encryption error: {e}")
        return None

# ✅ Create protobuf message
def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Protobuf creation error: {e}")
        return None

# ✅ Send like request asynchronously
async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB48"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                return await response.text() if response.status == 200 else None
    except Exception as e:
        app.logger.error(f"Error sending request: {e}")
        return None

# ✅ Send multiple like requests
async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if not protobuf_message:
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if not encrypted_uid:
            return None
        tokens = load_tokens(server_name)
        if not tokens:
            return None
        tasks = [send_request(encrypted_uid, tokens[i % len(tokens)]["token"], url) for i in range(100)]
        return await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        app.logger.error(f"Error in send_multiple_requests: {e}")
        return None

# ✅ Encode UID (Fixed)
def enc(uid, region):
    protobuf_data = create_protobuf_message(uid, region)
    return encrypt_message(protobuf_data) if protobuf_data else None

# ✅ Fetch player info
def make_request(encrypt, server_name, token):
    try:
        url = (
            "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
            if server_name == "IND"
            else "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
            if server_name in {"BR", "US", "SAC", "NA"}
            else "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
        )
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB48"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        
        # ✅ Debugging logs
        app.logger.info(f"Request URL: {url}")
        app.logger.info(f"Response Status: {response.status_code}")
        app.logger.info(f"Response Content: {response.text}")

        return decode_protobuf(response.content) if response.ok else None
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

# ✅ Decode protobuf response
def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        app.logger.error(f"Protobuf decoding error: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected protobuf decoding error: {e}")
        return None

# ✅ Handle API request
@app.route('/like', methods=['GET'])
async def handle_requests():
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "").upper()
    if not uid or not server_name:
        return jsonify({"error": "UID and server_name are required"}), 400

    try:
        tokens = load_tokens(server_name)
        if not tokens:
            raise Exception("Failed to load tokens.")
        token = tokens[0]['token']
        encrypted_uid = enc(uid, server_name)
        if not encrypted_uid:
            raise Exception("Encryption of UID failed.")

        # ✅ Fetch player info before likes
        before_data = make_request(encrypted_uid, server_name, token)
        if not before_data:
            raise Exception("Failed to fetch player info before liking.")
        data_before = json.loads(MessageToJson(before_data))
        before_like = int(data_before.get('AccountInfo', {}).get('Likes', 0))

        # ✅ Choose LikeProfile URL
        url = f"https://client.{server_name.lower()}.freefiremobile.com/LikeProfile"

        # ✅ Send likes asynchronously
        await send_multiple_requests(uid, server_name, url)

        # ✅ Fetch player info after likes
        after_data = make_request(encrypted_uid, server_name, token)
        if not after_data:
            raise Exception("Failed to fetch player info after liking.")
        data_after = json.loads(MessageToJson(after_data))
        after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0))
        like_given = after_like - before_like

        return jsonify({
            "LikesBefore": before_like,
            "LikesAfter": after_like,
            "LikesGiven": like_given,
            "PlayerUID": uid,
            "Status": "Success" if like_given else "Failed"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)