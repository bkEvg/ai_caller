from asterisk.ami import AMIClient

def on_event(event, source):
    print(f"Получено событие: {event}")

client = AMIClient(address='localhost', port=5038)
client.login(username='fastapi', secret='mysecret')

client.add_event_listener(on_event)
client.run()