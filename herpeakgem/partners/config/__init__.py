"""Configuration module for Partners channels."""

from herpeakgem.partners.config.paths import (
    get_data_dir,
    get_media_dir,
    get_partner_dir,
    get_partner_media_dir,
    get_partner_sessions_dir,
    get_partner_workspace,
    get_runtime_subdir,
)
from herpeakgem.partners.config.schema import Base, ChannelsConfig

__all__ = [
    "Base",
    "ChannelsConfig",
    "get_data_dir",
    "get_media_dir",
    "get_partner_dir",
    "get_partner_media_dir",
    "get_partner_sessions_dir",
    "get_partner_workspace",
    "get_runtime_subdir",
]
