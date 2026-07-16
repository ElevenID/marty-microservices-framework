"""Infrastructure adapters initialization."""

from .console_destination import ConsoleAuditDestination
from .database_destination import DatabaseAuditDestination
from .encryption_adapter import AuditEncryptionAdapter
from .file_destination import FileAuditDestination
from .siem_destination import SIEMAuditDestination

__all__ = [
    "ConsoleAuditDestination",
    "DatabaseAuditDestination",
    "FileAuditDestination",
    "SIEMAuditDestination",
    "AuditEncryptionAdapter",
]
