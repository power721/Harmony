from services.metadata.metadata_service import MetadataService


class _BrokenPathLike:
    def strip(self):
        return "broken"

    def __fspath__(self):
        raise RuntimeError("path construction failed")


def test_extract_metadata_handles_path_construction_failure():
    metadata = MetadataService.extract_metadata(_BrokenPathLike())

    assert metadata["title"] == ""
    assert metadata["artist"] == ""
    assert metadata["duration"] == 0.0
