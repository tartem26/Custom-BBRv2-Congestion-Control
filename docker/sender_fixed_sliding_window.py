import logging

from utils import FixedSlidingWindowSender

logging.basicConfig(level=logging.FATAL)
logger = logging.getLogger(__name__)

# Send the file
sender = FixedSlidingWindowSender(100)
sender.send('./file.mp3', 'localhost', 5001)
