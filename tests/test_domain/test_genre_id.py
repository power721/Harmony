from domain.genre import Genre


def test_empty_genres_do_not_share_same_generated_id():
    first = Genre(name="")
    second = Genre(name="")

    assert first.id != ""
    assert second.id != ""
    assert first.id != second.id
    assert first != second
