import logging
import logging.config

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%SZ',
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        }
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'json',
        }
    },
    'loggers': {
        '': {
            'handlers': ['stdout'],
            'level': 'INFO',
        }
    },
}


def configure_logging():
    logging.config.dictConfig(LOGGING)
