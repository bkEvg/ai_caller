import asterisk.manager

def on_event(event, manager):
    print(f"Получен звонок: {event}")

manager = asterisk.manager.Manager()
manager.connect('localhost')
manager.login('fastapi', 'mysecret')

manager.register_event('*', on_event)
manager.loop()