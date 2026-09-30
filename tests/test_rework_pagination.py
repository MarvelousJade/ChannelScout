import pytest

from channelscout.search import PAGE_SIZE, page


@pytest.mark.parametrize("count", [5, 6, 10, 11, 12, 15, 100])
def test_last_page_is_exact_snapshot_tail(count):
    snapshot = list(range(count))
    last_index = (count - 1) // PAGE_SIZE
    assert page(snapshot, last_index) == snapshot[last_index * PAGE_SIZE :]
    displayed = [row for index in range(last_index + 1) for row in page(snapshot, index)]
    assert displayed == snapshot


@pytest.mark.parametrize("count", [1, 5, 6, 100])
def test_page_after_tail_is_invalid(count):
    snapshot = list(range(count))
    with pytest.raises(ValueError, match="Invalid page"):
        page(snapshot, (count - 1) // PAGE_SIZE + 1)
    with pytest.raises(ValueError, match="Invalid page"):
        page(snapshot, -1)
