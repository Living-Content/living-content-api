"""SSL certificate generation service for internal container communication."""

import logging
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtensionOID, NameOID

from models.config import SSLConfig, SSLPaths

logger = logging.getLogger(__name__)


class SSLService:
    """Service for generating and managing SSL certificates."""

    def __init__(self, ssl_dir: Path, config: Optional[SSLConfig] = None) -> None:
        """Initialize SSL service.

        Args:
            ssl_dir: Directory to store SSL certificates
            config: SSL configuration
        """
        self.ssl_dir = ssl_dir
        self.ca_dir = ssl_dir / "ca"
        self.shared_dir = ssl_dir / "shared"
        self.config = config or SSLConfig()

    def setup_directories(self) -> None:
        """Create SSL directory structure."""
        self.ca_dir.mkdir(parents=True, exist_ok=True)
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created SSL directories at {self.ssl_dir}")

    def generate_ca_certificate(self) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
        """Generate Certificate Authority certificate.

        Returns:
            Tuple of (private_key, certificate)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, self.config.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, self.config.state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, self.config.locality),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.config.organization),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{self.config.organization} Internal CA"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(x509.datetime.datetime.now(x509.datetime.timezone.utc))
            .not_valid_after(
                x509.datetime.datetime.now(x509.datetime.timezone.utc)
                + x509.datetime.timedelta(days=3650)  # 10 years
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .sign(private_key, hashes.SHA256(), backend=default_backend())
        )

        logger.info("Generated CA certificate")
        return private_key, cert

    def generate_server_certificate(
        self,
        ca_key: rsa.RSAPrivateKey,
        ca_cert: x509.Certificate,
        common_name: str,
        san_dns: Optional[list[str]] = None,
        san_ip: Optional[list[str]] = None,
    ) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
        """Generate server certificate signed by CA.

        Args:
            ca_key: CA private key
            ca_cert: CA certificate
            common_name: Common name for certificate
            san_dns: Subject Alternative Name DNS entries
            san_ip: Subject Alternative Name IP entries

        Returns:
            Tuple of (private_key, certificate)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # Build subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Living Content"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Build SAN extension
        san_list = []
        if san_dns:
            san_list.extend([x509.DNSName(dns) for dns in san_dns])
        if san_ip:
            import ipaddress
            san_list.extend([x509.IPAddress(ipaddress.ip_address(ip)) for ip in san_ip])

        # Build certificate
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(x509.datetime.datetime.now(x509.datetime.timezone.utc))
            .not_valid_after(
                x509.datetime.datetime.now(x509.datetime.timezone.utc)
                + x509.datetime.timedelta(days=365)  # 1 year
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
                critical=False,
            )
        )

        if san_list:
            builder = builder.add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False,
            )

        cert = builder.sign(ca_key, hashes.SHA256(), backend=default_backend())

        logger.info(f"Generated server certificate for {common_name}")
        return private_key, cert

    def save_certificate(
        self,
        cert: x509.Certificate,
        key: rsa.RSAPrivateKey,
        cert_path: Path,
        key_path: Path,
        combined_path: Optional[Path] = None,
    ) -> None:
        """Save certificate and key to files.

        Args:
            cert: Certificate to save
            key: Private key to save
            cert_path: Path for certificate file
            key_path: Path for private key file
            combined_path: Optional path for combined PEM file
        """
        # Save certificate
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        cert_path.write_bytes(cert_pem)
        logger.debug(f"Saved certificate to {cert_path}")

        # Save private key
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path.write_bytes(key_pem)
        key_path.chmod(0o600)  # Restrict key file permissions
        logger.debug(f"Saved private key to {key_path}")

        # Save combined PEM if requested
        if combined_path:
            combined_pem = key_pem + cert_pem
            combined_path.write_bytes(combined_pem)
            combined_path.chmod(0o600)
            logger.debug(f"Saved combined PEM to {combined_path}")

    def generate_all_certificates(self) -> SSLPaths:
        """Generate all required certificates for the project.

        Returns:
            SSLPaths with paths to generated certificates
        """
        self.setup_directories()

        # Check if CA already exists
        ca_cert_path = self.ca_dir / "ca.crt"
        ca_key_path = self.ca_dir / "ca.key"

        if ca_cert_path.exists() and ca_key_path.exists():
            logger.info("CA certificate already exists, loading...")
            # Load existing CA
            ca_key_pem = ca_key_path.read_bytes()
            ca_cert_pem = ca_cert_path.read_bytes()
            ca_key = serialization.load_pem_private_key(
                ca_key_pem, password=None, backend=default_backend()
            )
            ca_cert = x509.load_pem_x509_certificate(ca_cert_pem, default_backend())
        else:
            # Generate new CA
            ca_key, ca_cert = self.generate_ca_certificate()
            self.save_certificate(
                ca_cert,
                ca_key,
                ca_cert_path,
                ca_key_path,
            )

        # Generate shared certificate for all services
        shared_key, shared_cert = self.generate_server_certificate(
            ca_key,
            ca_cert,
            "shared.livingcontent.local",
            san_dns=[
                "mongo",
                "redis",
                "api",
                "*.livingcontent.local",
                "localhost",
            ],
            san_ip=["127.0.0.1", "::1"],
        )

        shared_cert_path = self.shared_dir / "shared.crt"
        shared_key_path = self.shared_dir / "shared.key"
        shared_pem_path = self.shared_dir / "shared.pem"

        self.save_certificate(
            shared_cert,
            shared_key,
            shared_cert_path,
            shared_key_path,
            shared_pem_path,
        )

        return SSLPaths(
            ca_cert=str(ca_cert_path),
            ca_key=str(ca_key_path),
            shared_cert=str(shared_cert_path),
            shared_key=str(shared_key_path),
            shared_pem=str(shared_pem_path),
        )

    def verify_certificates(self) -> bool:
        """Verify that all required certificates exist.

        Returns:
            True if all certificates exist, False otherwise
        """
        required_files = [
            self.ca_dir / "ca.crt",
            self.ca_dir / "ca.key",
            self.shared_dir / "shared.crt",
            self.shared_dir / "shared.key",
            self.shared_dir / "shared.pem",
        ]

        for file in required_files:
            if not file.exists():
                logger.warning(f"Missing certificate file: {file}")
                return False

        logger.info("All SSL certificates verified")
        return True