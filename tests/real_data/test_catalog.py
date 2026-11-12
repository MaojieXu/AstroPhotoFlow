"""The authored corpus baseline covers every original without writing to it."""

from collections import Counter

from astropy.io import fits


def test_all_514_headers_and_explicit_group_members(real_data_root, real_data_catalog):
    paths = []
    for group in real_data_catalog['groups']:
        for member in group['members']:
            path = real_data_root / member['path']
            before = path.stat()
            header = fits.getheader(path)
            assert {key: header.get(key) for key in group['header']} == group['header']
            assert header['IMAGETYP'].upper() == 'LIGHT'
            assert (header['NAXIS1'], header['NAXIS2']) == (4656, 3520)
            assert header.get('OFFSET') is None
            assert header.get('CALSTAT') is None
            assert (path.stat().st_size, path.stat().st_mtime_ns) == (before.st_size, before.st_mtime_ns)
            paths.append(member['path'])
    for master in real_data_catalog['masters']:
        header = fits.getheader(real_data_root / master['path'])
        assert {key: header.get(key) for key in master['header']} == master['header']
        assert str(header['IMAGETYP']).casefold() in {'master dark', 'master flat'}
        assert all(header.get(key) is None for key in ('GAIN', 'OFFSET', 'CCD-TEMP', 'CALSTAT'))
        paths.append(master['path'])
    assert len(paths) == len(set(paths)) == real_data_catalog['total_files'] == 514
    assert Counter(path.split('/')[0] for path in paths) == real_data_catalog['source_folders']


def test_filter_labels_camera_names_and_exact_temperatures_stay_distinct(real_data_root, real_data_catalog):
    groups = real_data_catalog['groups']
    rgb0 = Counter({})
    rgb1 = Counter({})
    for group in groups:
        if group['source_folder'] == 'IC443_RGB_P0':
            rgb0[group['header']['FILTER']] += len(group['members'])
        if group['source_folder'] == 'IC443_RGB_P1':
            rgb1[group['header']['FILTER']] += len(group['members'])
    assert rgb0 == {'Green': 35, 'Blue': 31, 'Red': 27}
    assert rgb1 == {'Green': 16, 'Blue': 13, 'Red': 12, 'R': 21, 'G': 16, 'B': 16}
    sho2 = [group for group in groups if group['source_folder'] == 'IC443_SHO_P2']
    assert len({group['header']['INSTRUME'] for group in sho2}) == 2
    assert {group['header']['CCD-TEMP'] for group in sho2} == {-16, -15.5, -16.5, -18}
    assert len(real_data_catalog['groups']) == 30
