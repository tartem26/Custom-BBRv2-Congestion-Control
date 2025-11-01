import logging

from utils import TahoeRenoSender

logging.basicConfig(level=logging.FATAL)
logger = logging.getLogger(__name__)

# Send the file
sender = TahoeRenoSender('T')
sender.send('./file.mp3', 'localhost', 5001)
