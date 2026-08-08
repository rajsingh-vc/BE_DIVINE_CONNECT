import ssl

from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


class RelaxedSSLEmailBackend(SMTPEmailBackend):
    """
    DEV-ONLY workaround for local Windows machines where antivirus (or a
    VPN) intercepts TLS and injects a root certificate that doesn't mark
    its X.509 Basic Constraints as 'critical' per RFC 5280. Python 3.13's
    stricter VERIFY_X509_STRICT check now rejects that, causing:
        ssl.SSLCertVerificationError: ... Basic Constraints of CA cert
        not marked critical

    This only disables that one specific strict flag — normal certificate
    validation (hostname, chain of trust, expiry) still applies. Do not
    use in production; fix the intercepting antivirus/VPN there instead.
    """

    @property
    def ssl_context(self):
        context = ssl.create_default_context()
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return context