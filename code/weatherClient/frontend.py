import requests

resp = requests.get("https://localhost:8080/")
obj = resp.json()
print(type(obj))
# <class 'dict'>
print(obj)
