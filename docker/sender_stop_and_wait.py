import logging

from utils import StopAndWaitSender

logging.basicConfig(level=logging.FATAL)
logger = logging.getLogger(__name__)

# Send the file
sender = StopAndWaitSender()
sender.send('./file.mp3', 'localhost', 5001)
