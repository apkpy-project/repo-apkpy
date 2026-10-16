# -*- coding: utf-8 -*-
"""Certificate pinning -- deciding which certificate counts for a host.

    from apkpy_lib import https

    https.pin("api.example.com", [
        "sha256/K87oWBWM9UZfyddvDfoxL+8lpNyoUB2ptGtn0fv6G2Q=",   # in use
        "sha256/JbQbUG5JMJUoI6brnx0x3vZF6jilxsapbXGVfjhN8Fg=",   # the next one
    ], expires="2027-06-01")

Android checks that the server's certificate chains to a trusted authority. It
does not check *which* authority -- so anyone who can get a certificate a phone
trusts can read the traffic, and on a managed device that includes whoever
installed the company's own root. Pinning says which public key is acceptable
for one host, and nothing else is.

**Written as configuration, not as code.** The pins go into
``res/xml/apkpy_network_security.xml``, which Android applies underneath every
HTTP stack in the app. Enforcing this in code would only cover the requests
that remembered to ask.

**Two pins, and the second one is not optional.** A pinned app whose only pin
is the certificate in use stops reaching its own server the day that
certificate is replaced -- for everybody, at once, with no way back except a
store update that the person may not install for weeks. The backup pin is the
difference between a routine renewal and an outage, so this refuses to write a
pin set with only one.
"""

import re

# Android's own format: the base64 of a SHA-256 over the SubjectPublicKeyInfo.
PIN_PATTERN = re.compile(r'^sha256/[A-Za-z0-9+/]{43}=$')

# A hostname, or a wildcard-free domain. Android matches subdomains through
# includeSubdomains rather than through a star, so a star here would silently
# pin nothing.
HOST_PATTERN = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)'
                          r'(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$')

EXPIRES_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

MINIMUM_PINS = 2

DOCS = 'https://repo-apkpy.pages.dev/data-security/'


def check_host(host):
    """Why this host cannot be pinned, or ''."""
    text = str(host or '').strip().lower()
    if not text:
        return 'a host is needed, for example "api.example.com"'
    if text.startswith('*'):
        return ('Android matches subdomains with include_subdomains, not with '
                'a star -- a star here would pin nothing at all')
    if '/' in text or ':' in text:
        return 'give the host on its own, without a scheme, port or path'
    if not HOST_PATTERN.match(text):
        return '%r is not a hostname' % host
    return ''


def check_pins(pins):
    """Why this pin set cannot be written, or ''."""
    values = list(pins or [])
    for pin in values:
        if not PIN_PATTERN.match(str(pin)):
            return ('%r is not a pin. Android wants the base64 of a SHA-256 '
                    'over the certificate\'s public key, written as '
                    '"sha256/....="' % (pin,))
    if len(set(values)) != len(values):
        return 'the same pin is listed twice, which leaves only one real pin'
    if len(values) < MINIMUM_PINS:
        return ('only one pin. The day that certificate is replaced the app '
                'stops reaching this host -- for everyone, at once, and only a '
                'store update fixes it. Add the pin of the next certificate, '
                'or of the issuing authority, as a spare')
    return ''


def check_expires(expires):
    if expires is None:
        return ''
    if not EXPIRES_PATTERN.match(str(expires)):
        return 'an expiry is written as YYYY-MM-DD'
    return ''


def normalise(host):
    return str(host).strip().lower()


def network_security_xml(entries, debug_overrides=True):
    """``res/xml/apkpy_network_security.xml``.

    *entries* is host -> {"pins": [...], "expires": "YYYY-MM-DD" or None,
    "subdomains": bool}.

    ``debug-overrides`` lets a **debug** build keep trusting certificates the
    developer installed, so a proxy still works while building. Android ignores
    the block entirely unless the app is debuggable, so a release build is
    unaffected -- and without it, turning pinning on would mean never being
    able to look at your own traffic again.
    """
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<network-security-config>']
    if debug_overrides:
        lines += [
            '    <!-- Only applied when the app is debuggable. A release build',
            '         never reads this block. -->',
            '    <debug-overrides>',
            '        <trust-anchors>',
            '            <certificates src="system" />',
            '            <certificates src="user" />',
            '        </trust-anchors>',
            '    </debug-overrides>',
        ]
    for host in sorted(entries):
        entry = entries[host]
        subdomains = 'true' if entry.get('subdomains') else 'false'
        lines.append('    <domain-config>')
        lines.append('        <domain includeSubdomains="%s">%s</domain>'
                     % (subdomains, host))
        expires = entry.get('expires')
        lines.append('        <pin-set expiration="%s">' % expires
                     if expires else '        <pin-set>')
        for pin in entry.get('pins', []):
            lines.append('            <pin digest="SHA-256">%s</pin>'
                         % str(pin).split('/', 1)[1])
        lines.append('        </pin-set>')
        lines.append('    </domain-config>')
    lines.append('</network-security-config>')
    return '\n'.join(lines) + '\n'
