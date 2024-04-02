import sys

# Check that we're not running on an unsupported Python version.
if sys.version_info < (3, 5):
    print("nio_channel_bot requires Python 3.5 or above.")
    sys.exit(1)

__version__ = "1.0.0"
