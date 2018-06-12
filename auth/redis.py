import redis as redis


class ConnectLaterRedis:
    def __init__(self):
        self.__redis = None

    def _connect(self, url):
        self.__redis = redis.StrictRedis.from_url(url)

    def __getattr__(self, item):
        return getattr(self.__redis, item)


client = ConnectLaterRedis()


def init_app(app):
    client._connect(app.config['REDIS_URL'])

