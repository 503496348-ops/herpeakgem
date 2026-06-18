"""Message bus module for decoupled channel-agent communication."""

from herpeakgem.partners.bus.events import InboundMessage, OutboundMessage
from herpeakgem.partners.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
