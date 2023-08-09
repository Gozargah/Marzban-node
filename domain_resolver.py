import socket
import re


def _is_domain_test(context):
    pattern = re.compile("[a-z]")
    match = pattern.search(context)
    if match is None:
        return False
    else:
        return True


def resolve_domain(domain):
    is_domain = _is_domain_test(domain)
    if is_domain is False:
        return [domain]
    else:
        try:
            result = socket.getaddrinfo(domain, None)
            ip_addresses_list = [info[4][0] for info in result]
            return ip_addresses_list
        except socket.gaierror as e:
            raise socket.gaierror(f"Error while getting address for ({domain})!! [{e}]")
