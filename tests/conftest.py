import pytest
from fakes import FakeEagle, FakeSite

from yk2eagle.moebooru import MoebooruClient, make_session


@pytest.fixture
def site():
    with FakeSite() as server:
        yield server


@pytest.fixture
def fake_eagle():
    with FakeEagle() as server:
        yield server


@pytest.fixture
def quick_client(site):
    """A client for the fake site that does not wait between requests or before retries."""
    return MoebooruClient(site.url, session=make_session(backoff_factor=0), interval=0, page_size=3)
