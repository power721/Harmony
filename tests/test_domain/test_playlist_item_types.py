from domain.playlist_item import PlaylistItem


def test_from_dict_coerces_track_id_and_duration_types():
    item = PlaylistItem.from_dict(
        {
            "id": "12",
            "duration": "245.5",
            "title": "Song",
        }
    )

    assert item.track_id == 12
    assert isinstance(item.track_id, int)
    assert item.duration == 245.5
    assert isinstance(item.duration, float)
