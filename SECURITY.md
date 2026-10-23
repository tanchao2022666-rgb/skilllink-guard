# Security policy

v0.1.x is the initial maintained development line; no remote release is claimed.

After publication, use the repository's Security → Report a vulnerability
(GitHub Private Vulnerability Reporting) if it is enabled. If unavailable,
contact the maintainer privately using their published GitHub profile contact
method. No maintainer identity or email is invented here. Do not disclose private
Skill contents, credentials, or an unpatched exploit in a public issue. A public
issue may request a private contact channel without exploit details.

Include version, Python/OS, minimal synthetic reproduction, expected boundary,
and impact. The tool does not execute input commands, fetch links, or read
referenced resources' contents; escape targets must not be inspected for
existence. Discovery does not follow links/junctions. This is not a general
security audit, malicious-content detector, or replacement for OS isolation.
Concurrent hostile filesystem changes and filesystem race protection are not
covered by v0.1. Scan stable trees and review scripts independently before use.

Discovery uses non-following entry metadata even when classifying a directory.
Symbolic link `..` components are processed in filesystem order. Ambiguous
Windows aliases/device spellings are not queried. Input-derived CLI error
messages cannot emit additional raw workflow command lines.

Dependency installation and GitHub Action execution use the normal Python/GitHub
supply chain and are separate from the scanner's offline, non-executing behavior.
Pin reviewed action commits and dependencies according to your own policy.
