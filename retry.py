import random

# Real proxies can be added here later if needed.
# Example:
# PROXY_LIST = ["http://username:password@proxy-ip:port"]

PROXY_LIST = []


def get_proxy():
    """
    Selects a random proxy.
    If no proxy is available, it uses normal direct request.
    """

    if not PROXY_LIST:
        print("[Proxy] No proxy configured. Using direct request.")
        return None

    selected_proxy = random.choice(PROXY_LIST)

    print("[Proxy] Using:", selected_proxy)

    return {
        "http": selected_proxy,
        "https": selected_proxy
    }


def demo_proxy_rotation():
    demo_proxies = [
        "Proxy A",
        "Proxy B",
        "Proxy C"
    ]

    return random.choice(demo_proxies)