import os
import py_compile
import sys

import pytest

from astrophotoflow.modules.software.bundles.loader import load_adapter
from astrophotoflow.modules.software.development import content_fingerprint


def write_bundle(root):
    (root / 'adapter').mkdir(parents=True)
    (root / 'bundle.json').write_text(
        '{"adapter":"adapter/main.py","operations":[],"nodes":[]}'
    )
    (root / 'adapter/main.py').write_text('from .helper import value\nVALUE = value()\n')
    helper = root / 'adapter/helper.py'
    helper.write_text('def value(): return 1\n')
    return helper


def test_complete_namespace_reloads_same_size_same_timestamp_helper_without_stale_bytecode(tmp_path):
    helper = write_bundle(tmp_path)
    py_compile.compile(str(helper), doraise=True)
    before = helper.stat()
    first = load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path))
    helper.write_text('def value(): return 2\n')
    os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert helper.stat().st_size == before.st_size
    assert helper.stat().st_mtime_ns == before.st_mtime_ns
    second = load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path))
    assert first.VALUE == 1 and second.VALUE == 2
    assert first is not second
    assert sys.modules[first.__name__] is second
    assert load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path)) is second


def test_new_deleted_and_broken_helpers_do_not_reuse_previous_success(tmp_path):
    helper = write_bundle(tmp_path)
    first = load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path))
    py_compile.compile(str(helper), doraise=True)
    helper.unlink()
    with pytest.raises(ModuleNotFoundError):
        load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path))
    assert not any(name == first.__package__ or name.startswith(first.__package__ + '.')
                   for name in sys.modules)
    helper.write_text('from .extra import VALUE\ndef value(): return VALUE\n')
    extra = helper.with_name('extra.py')
    extra.write_text('VALUE = 3\n')
    assert load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path)).VALUE == 3
    extra.write_text('raise ValueError("broken helper")\n')
    with pytest.raises(ValueError, match='broken helper'):
        load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path))
    extra.write_text('VALUE = 4\n')
    assert load_adapter(tmp_path, 'adapter/main.py', content_fingerprint(tmp_path)).VALUE == 4


def test_bundles_have_distinct_namespaces_and_support_dataclasses(tmp_path):
    roots = [tmp_path / 'first', tmp_path / 'second']
    loaded = []
    for index, root in enumerate(roots):
        write_bundle(root)
        (root / 'adapter/helper.py').write_text(
            'from dataclasses import dataclass\n'
            '@dataclass\nclass Value:\n    number: int\n'
            f'def value(): return Value({index})\n'
        )
        loaded.append(load_adapter(root, 'adapter/main.py', content_fingerprint(root)))
    assert [module.VALUE.number for module in loaded] == [0, 1]
    assert type(loaded[0].VALUE) is not type(loaded[1].VALUE)


@pytest.mark.parametrize('entry', ['../escape.py', '/outside.py', 'adapter/bad-name.py', 'adapter/main.pyc'])
def test_adapter_entry_must_be_a_contained_python_module(tmp_path, entry):
    with pytest.raises(ValueError, match='contained Python module'):
        load_adapter(tmp_path, entry, 'invalid')
