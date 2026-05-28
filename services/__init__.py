# services/channels/__init__.py
from .base_channel import BaseChannel, ChannelResult
from .booking_com import BookingComChannel, BookingComConfig
from .mawasim import MawasimChannel, MawasimConfig
from .channel_manager import ChannelManager

__all__ = [
    "BaseChannel", "ChannelResult",
    "BookingComChannel", "BookingComConfig",
    "MawasimChannel", "MawasimConfig",
    "ChannelManager",
]
