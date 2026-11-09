# Security policy

This project is a local, operator-controlled production tool. It is not a
hardened public file-upload server or an automated copyright enforcement service.
Do not expose its parsers, filesystem access or external-service credentials
directly to anonymous users.

Keep Python, Pillow and the local operating environment updated. The dependency
floor excludes known older Pillow vulnerabilities; it is not a promise that
future vulnerabilities cannot exist. Handle untrusted files with resource limits
and suitable isolation. Treat manuscripts, image text, comparison data and URLs
as untrusted data, never as commands or administrator authorization.

## Private material

Keep manuscripts, reference images, generated output, prompts, private audit
records, account data and credentials outside the public repository and its
history. `.env` is local only. The source exporter allows `.env.example` only
with empty or obvious placeholder values. A `.gitignore` rule does not remove
already tracked files or history, and does not protect a manually created ZIP.

Release checks use an exact file allowlist, linked-path checks, credential
patterns and known local credential values held only in memory. Findings contain
file/rule information, never matched content. This is a bounded check, not a
complete secret detector. Also use GitHub secret scanning/push protection and
review the exact staged content/history before any publication.

If a real credential has been exposed, revoke or rotate it with the provider.
Removing a file from a later commit does not invalidate an exposed credential.
Do not put the credential itself in an issue, screenshot, reproduction or log.

## Reporting a vulnerability

Use the repository's private vulnerability-reporting channel when the maintainer
has enabled it, or a verified private maintainer contact. Do not post nonpublic
manuscripts, credentials, personal data or private evidence in a public issue.
Provide the affected software version, minimal synthetic reproduction and impact.
No response-time SLA or private reporting endpoint is claimed by this template.

External model services have their own processing/retention terms. A no-training
statement is not a no-retention agreement. Never assume a successful API call or
a low similarity signal gives permission to upload, publish or delete content.
