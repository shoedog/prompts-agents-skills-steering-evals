def fetch(client):
    try:
        return client.get()
    except TimeoutError:
        return None
