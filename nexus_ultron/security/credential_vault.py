"""Windows Credential Manager + Encrypted Local Vault for API keys and OAuth tokens."""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .audit_logger import AuditLogger

logger = logging.getLogger("nexus_ultron.vault")

SERVICE_NAMESPACE = "NEXUS_ULTRON_V3"

# Prohibited credential categories (never store payment/banking credentials or raw Gmail passwords)
_PROHIBITED_KEY_FRAGMENTS = (
    "card_number",
    "credit_card",
    "debit_card",
    "cvv",
    "upi_pin",
    "bank_password",
    "netbanking",
    "gmail_raw_password",
)


class CredentialVaultError(PermissionError):
    """Raised when attempting to store prohibited credentials."""


class CredentialVault:
    """
    Stores authorized API keys & OAuth tokens using Windows Credential Manager (via keyring
    WinVaultKeyring on Windows 10) with an AES-128-CBC+HMAC (Fernet) PBKDF2 encrypted local vault fallback.
    """

    def __init__(self, vault_dir: Path, audit: AuditLogger | None = None) -> None:
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.vault_file = self.vault_dir / "credentials.vault"
        self.salt_file = self.vault_dir / "vault.salt"
        self.audit = audit
        self._fernet = self._init_fernet()
        self._windows_credman_available = self._check_windows_credman()

    @staticmethod
    def _check_windows_credman() -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import keyring

            backend = keyring.get_keyring()
            return "WinVault" in type(backend).__name__ or "Windows" in type(backend).__name__
        except Exception:
            return False

    def _init_fernet(self) -> Fernet:
        if not self.salt_file.exists():
            salt = os.urandom(32)
            self.salt_file.write_bytes(salt)
            try:
                os.chmod(self.salt_file, 0o600)
            except OSError:
                pass
        else:
            salt = self.salt_file.read_bytes()

        machine_binding = f"{platform.node()}|{os.name}|{self.vault_dir.resolve()}".encode("utf-8")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=200_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_binding))
        return Fernet(key)

    def _read_local_vault(self) -> dict[str, str]:
        if not self.vault_file.exists():
            return {}
        try:
            decrypted = self._fernet.decrypt(self.vault_file.read_bytes())
            data = json.loads(decrypted.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("Encrypted vault could not be decrypted (%s); starting fresh map.", exc)
            return {}

    def _write_local_vault(self, mapping: dict[str, str]) -> None:
        encrypted = self._fernet.encrypt(json.dumps(mapping).encode("utf-8"))
        self.vault_file.write_bytes(encrypted)
        try:
            os.chmod(self.vault_file, 0o600)
        except OSError:
            pass

    @staticmethod
    def _validate_key_name(key_name: str) -> None:
        lower = (key_name or "").strip().lower()
        if not lower:
            raise ValueError("Credential key name cannot be empty")
        for bad in _PROHIBITED_KEY_FRAGMENTS:
            if bad in lower:
                raise CredentialVaultError(
                    f"Credential '{key_name}' is prohibited by NEXUS ULTRON Security Policy "
                    f"(payment credentials and raw Gmail passwords are never stored)."
                )

    def set_secret(self, key_name: str, secret_value: str) -> str:
        self._validate_key_name(key_name)
        backend_used = "encrypted_local_vault"
        if self._windows_credman_available:
            try:
                import keyring

                keyring.set_password(SERVICE_NAMESPACE, key_name, secret_value)
                backend_used = "windows_credential_manager"
            except Exception as exc:
                logger.debug("Windows Credential Manager fallback to encrypted local vault: %s", exc)

        data = self._read_local_vault()
        data[key_name] = secret_value
        self._write_local_vault(data)

        if self.audit:
            self.audit.log_event(
                event_type="credential_stored",
                actor="user",
                category="security_vault",
                decision="allowed",
                details=f"Stored credential '{key_name}' via {backend_used}",
            )
        return backend_used

    def get_secret(self, key_name: str) -> str | None:
        self._validate_key_name(key_name)
        # Check environment override first if provided by user
        env_val = os.environ.get(key_name.upper())
        if env_val:
            return env_val

        if self._windows_credman_available:
            try:
                import keyring

                val = keyring.get_password(SERVICE_NAMESPACE, key_name)
                if val:
                    return val
            except Exception:
                pass

        return self._read_local_vault().get(key_name)

    def delete_secret(self, key_name: str) -> bool:
        if self._windows_credman_available:
            try:
                import keyring

                keyring.delete_password(SERVICE_NAMESPACE, key_name)
            except Exception:
                pass
        data = self._read_local_vault()
        removed = key_name in data
        if removed:
            del data[key_name]
            self._write_local_vault(data)
            if self.audit:
                self.audit.log_event(
                    event_type="credential_deleted",
                    actor="user",
                    category="security_vault",
                    decision="allowed",
                    details=f"Deleted credential '{key_name}'",
                )
        return removed

    def list_stored_keys(self) -> list[dict[str, Any]]:
        """Return metadata about stored keys WITHOUT exposing secret values."""
        data = self._read_local_vault()
        out = []
        for k, val in sorted(data.items()):
            masked = f"{val[:3]}...{val[-2:]}" if len(val) >= 8 else "****"
            out.append(
                {
                    "key_name": k,
                    "masked_preview": masked,
                    "backend": "windows_credential_manager+aes_vault"
                    if self._windows_credman_available
                    else "aes_fernet_vault",
                }
            )
        return out
