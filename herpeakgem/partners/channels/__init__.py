"""Chat channels module with plugin architecture."""

from herpeakgem.partners.channels.base import BaseChannel
from herpeakgem.partners.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
