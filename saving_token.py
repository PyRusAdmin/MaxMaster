

token = data["payload"]["token"]
with open("token.txt", "w") as f:
    f.write(token)
