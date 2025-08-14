import json

# Допустим, json_data — это твой ответ сервера
data = json.loads(json_data)

# Достаём чаты
chats = data["payload"]["chats"]

for chat in chats:
    chat_id = chat["id"]
    chat_type = chat["type"]
    last_msg = chat.get("lastMessage", {})
    print(f"ID: {chat_id}, Type: {chat_type}, Last message: {last_msg.get('text', '')}")
