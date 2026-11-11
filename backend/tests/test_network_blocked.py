import socket

import pytest
from pytest_socket import SocketBlockedError


def test_tests_cannot_open_network_sockets():
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
