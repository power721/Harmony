from domain.genre import Genre


def test_empty_genres_do_not_share_same_generated_id():
    first = Genre(name="")
    second = Genre(name="")

    assert first.id != ""
    assert second.id != ""
    assert first.id != second.id
    assert first != second


def test_named_genre_id_is_stable_across_accesses():
    genre = Genre(name="Rock")

    first = genre.id
    second = genre.id

    assert first == "rock"
    assert second == "rock"
