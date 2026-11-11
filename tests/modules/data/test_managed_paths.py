import os
from pathlib import Path

import pytest

from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.files import managed_data_path


@pytest.mark.skipif(os.name != 'nt', reason='Windows extended path syntax')
@pytest.mark.parametrize('outside', [False, True])
def test_managed_path_checks_extended_windows_paths(tmp_path, monkeypatch, outside):
    root = tmp_path.resolve() / 'data'
    root.mkdir()
    relative = Path('staging', 'output.part')
    lexical = root / relative
    resolved = root.parent / 'other' / relative if outside else lexical
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == lexical:
            return Path('\\\\?\\' + str(resolved))
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'resolve', resolve)
    if outside:
        with pytest.raises(ApiError) as error:
            managed_data_path(root, relative)
        assert error.value.code == 'FILE_SCOPE_INVALID'
    else:
        assert managed_data_path(root, relative) == lexical
