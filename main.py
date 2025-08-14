import json
import os
import sys
from uuid import uuid4

from dotenv import load_dotenv  # для загрузки переменных из .env
from websockets.sync.client import connect

# Загружаем .env
load_dotenv()


class MaxClient:
    def __init__(self, phone_number):
        print("Welcome to MaxLib 0.1!")
        self.phone_number = phone_number
        self.auth_token = None
        self.user_agent = self._generate_user_agent()
        self.websocket = None

    def _generate_user_agent(self) -> str:
        return json.dumps({
            "ver": 11,
            "cmd": 0,
            "seq": 0,
            "opcode": 6,
            "payload": {
                "userAgent": {
                    "deviceType": "WEB",
                    "locale": "ru_RU",
                    "osVersion": "Linux",
                    "deviceName": "Firefox",
                    "headerUserAgent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
                    "deviceLocale": "ru-RU",
                    "appVersion": "4.8.42",
                    "screen": "1080x1920 1.0x",
                    "timezone": "Europe/Moscow"
                },
                "deviceId": str(uuid4())
            }
        })

    def _connect(self):
        self.websocket = connect("wss://ws-api.oneme.ru/websocket")
        self.websocket.send(self.user_agent)
        self.websocket.recv()

    def _disconnect(self):
        if self.websocket:
            self.websocket.close()

    def _die(self):
        if self.websocket:
            self.websocket.close()
        sys.exit()

    def authenticate(self) -> str:
        """Authenticate and save token"""
        self._connect()

        self.websocket.send(json.dumps({
            "ver": 11,
            "cmd": 0,
            "seq": 3,
            "opcode": 17,
            "payload": {
                "phone": self.phone_number,
                "type": "START_AUTH",
                "language": "ru"
            }
        }))

        code_resp = json.loads(self.websocket.recv())
        if code_resp.get('payload', {}).get('error'):
            raise ValueError(code_resp['payload']['error'] + ": " + code_resp['payload']['localizedMessage'])
            self._die()

        token = code_resp['payload']['token']
        print("Auth token received. Please enter the code sent to your phone.")

        code = input("Auth code: ")
        self.websocket.send(json.dumps({
            "ver": 11,
            "cmd": 0,
            "seq": 8,
            "opcode": 18,
            "payload": {
                "token": token,
                "verifyCode": code,
                "authTokenType": "CHECK_CODE"
            }
        }))

        token_resp = json.loads(self.websocket.recv())
        self.auth_token = token_resp['payload']['tokenAttrs']['LOGIN']['token']

        with open("token.txt", "w") as f:
            f.write(self.auth_token)

        self._disconnect()
        return self.auth_token

    def get_chats(self):
        if not self.auth_token:
            raise ValueError("No auth token provided. Please authenticate first.")

        self._connect()
        self.websocket.send(json.dumps({
            "ver": 11,
            "cmd": 0,
            "seq": 9,
            "opcode": 19,
            "payload": {
                "interactive": True,
                "token": self.auth_token,
                "chatsSync": 0,
                "contactsSync": 0,
                "presenceSync": 0,
                "draftsSync": 0,
                "chatsCount": 40
            }
        }))

        response = self.websocket.recv()
        self._disconnect()
        return json.loads(response)


if __name__ == "__main__":
    phone_number = os.getenv("PHONE_NUMBER")  # Читаем из .env

    if not phone_number:
        print("PHONE_NUMBER is not set in .env")
        sys.exit(1)

    client = MaxClient(phone_number)

    if os.path.exists("token.txt"):
        with open("token.txt", "r") as f:
            client.auth_token = f.read().strip()
        print("Используем сохранённый токен.")
    else:
        client.authenticate()

    data = client.get_chats()
    chats = data["payload"]["chats"]

    for chat in chats:
        chat_id = chat["id"]
        chat_type = chat["type"]
        last_msg = chat.get("lastMessage", {})
        print(f"ID: {chat_id}, Type: {chat_type}, Last message: {last_msg.get('text', '')}")
