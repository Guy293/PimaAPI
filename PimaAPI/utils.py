from time import sleep


def retry(exception, attempts, delay=0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(attempts):
                try:
                    func(*args, **kwargs)
                    return
                except exception as ex:
                    print(
                        f"{type(ex).__name__} exception raised. Retrying in {delay} seconds..."
                    )
                    if i == attempts - 1:
                        raise ex
                    sleep(delay)

        return wrapper

    return decorator


def crc16_xmodem(data):
    crc = 0
    user_mask = 65535
    for b in data:
        for i in range(8):
            bit = (b >> (7 - i)) & 1
            c15 = (crc >> 15) & 1
            crc <<= 1
            if c15 ^ bit:
                crc ^= 4129
    return (crc & user_mask).to_bytes(2, byteorder="big")
