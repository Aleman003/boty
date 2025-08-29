import json, requests, time

URL = "http://127.0.0.1:3000/webhook"

def send_text(wa_id: str, text: str, name: str = "Cliente Demo"):
    payload = {
      "object": "whatsapp_business_account",
      "entry": [{
        "id": "TEST_ID",
        "changes": [{
          "field": "messages",
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "15551112222", "phone_number_id": "PHONE_ID_TEST"},
            "contacts": [{"profile": {"name": name}, "wa_id": wa_id}],
            "messages": [{
              "from": wa_id,
              "id": f"wamid.TEST.{int(time.time())}",
              "timestamp": str(int(time.time())),
              "text": {"body": text},
              "type": "text"
            }]
          }
        }]
      }]
    }
    r = requests.post(URL, json=payload, timeout=10)
    print("POST", r.status_code, r.text[:200])

if __name__ == "__main__":
    W = "5218128793882"
    send_text(W, "Hola")
    time.sleep(0.6)
    send_text(W, "Soy Karla")
    time.sleep(0.6)
    send_text(W, "Quiero renovar")
    time.sleep(0.6)
    send_text(W, "Venció en febrero de 2023")
