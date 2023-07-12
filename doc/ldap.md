# LDAP tool comparisson

The are two main LDAP implementations for Linux: OpenLDAP and 389.
OpenLDAP was the de-facto standard for many years but many distros have replaced it by 389 menwhile.
389 is more modern and has better documentation -- specially when it comes to TLS encrypted LDAP (LDAPS). The downside is that it's extremely hard to containerize 389 and there are no off-the-shelf solutions. So for K8s we need to stick to OpenLDAP.