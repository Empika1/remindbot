import logging

logging.basicConfig(filename="errlog.txt", encoding="utf-8", format="%(asctime)s %(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)

errlog = open('errlog.txt', "a+")
logger.info("Logging session started.")

def log_err(err: Exception):
    logger.exception(err)

errlog.close()