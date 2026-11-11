# Security

Please report vulnerabilities privately through GitHub's "Report a vulnerability" (Security tab) rather than a public issue.

The SDK never handles private keys. It sends a per-run credential (`trt_…`) to the Tarmac server you configure; treat it like a password for that one run.
