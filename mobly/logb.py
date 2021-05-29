import logging
import os
import coloredlogs


################################
# Constants
################################
MODU_PATH = os.path.dirname(__file__) if os.path.dirname(__file__) else './'
''' Path of current module '''

LOGGER_FORMAT = "[%(levelno)s|%(module)s|%(lineno)s] %(message)s"
''' Format of Logger '''

LOGGER_LEVEL = 10  # CRITICAL=50; ERROR=40; WARNING=30; INFO=20; DEBUG=10
''' Message level of Logger '''


################################
# Constants
################################
def get_logger(name, level=LOGGER_LEVEL, fmt=LOGGER_FORMAT):
  logger = logging.getLogger(name)
  logger.setLevel(level)
  logger.propagate = False
  coloredlogs.install(level=level, logger=logger, fmt=fmt)
  return logger
