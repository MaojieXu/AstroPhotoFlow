from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

from astrophotoflow.contracts.assets import LibraryQuery
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.library.queries import search_library
from astrophotoflow.modules.data.persistence import schema_metadata


def asset_entry(record_id, *, name=None, parameters=None, classification=None, storage_mode="managed"):
    asset = {
        "id": record_id, "name": name or record_id, "role": "raw", "status": "active", "notes": None,
        "classification": classification or {}, "parameters": parameters or {},
        "current_version": {"storage_mode": storage_mode},
    }
    return {"entry_type": "asset", "id": record_id, "asset": asset, "sort_created_at": "2026-10-23"}


def dataset_entry(record_id, members):
    return {
        "entry_type": "dataset", "id": record_id, "sort_created_at": "2026-10-23",
        "dataset": {"id": record_id, "name": record_id, "status": "active", "notes": None},
        "version": {"members": [
            {"asset": member["asset"], "version": member["asset"]["current_version"]}
            for member in members
        ]},
    }


def ordered(entries, sort_by, order):
    def identity(value):
        return str(uuid5(NAMESPACE_URL, "library-sort/" + value))

    with TemporaryDirectory(prefix="apf-library-order-") as temporary:
        database = Database(Path(temporary) / "catalog.sqlite3")
        schema_metadata().create_all(database.engine)
        labels = {}
        try:
            with database.write_session() as session:
                for entry in entries:
                    kind, label = entry["entry_type"], entry["id"]
                    entry_id = identity(kind + "/" + label)
                    labels[kind, entry_id] = label
                    inputs = [{"asset": entry["asset"], "version": entry["asset"]["current_version"]}] if kind == "asset" else entry["version"]["members"]
                    if kind == "dataset":
                        dataset = Dataset(id=entry_id, name=entry["dataset"]["name"], created_at=datetime(2026, 10, 23, tzinfo=UTC))
                        session.add(dataset); session.flush()
                        fixed = DatasetVersion(id=identity("fixed/" + label), dataset_id=entry_id, version_number=1)
                        session.add(fixed); session.flush()
                        dataset.current_version_id = fixed.id
                    for position, member in enumerate(inputs):
                        source = member["asset"]
                        asset_id = entry_id if kind == "asset" else identity("member/" + label + "/" + str(position))
                        parameters = dict(source["parameters"])
                        snapshots = {}
                        for key in ("camera_id", "optical_system_id", "filter_id"):
                            if parameters.get(key):
                                parameters[key] = identity("device/" + parameters[key])
                            if source.get("equipment_snapshot", {}).get(key):
                                snapshots[key] = {**source["equipment_snapshot"][key], "id": parameters.get(key)}
                        asset = Asset(id=asset_id, name=source["name"], scope="shared", role="raw", equipment_snapshot=snapshots,
                                      created_at=datetime(2026, 10, 23, tzinfo=UTC), **parameters, **source["classification"])
                        session.add(asset); session.flush()
                        version = AssetVersion(id=identity("version/" + asset_id), asset_id=asset_id, version_number=1,
                            storage_mode=member["version"]["storage_mode"], storage_location="unused.fit", byte_size=1,
                            content_hash="b3:" + "a" * 64, availability="available")
                        session.add(version); session.flush(); asset.current_version_id = version.id
                        if kind == "dataset":
                            session.add(DatasetMember(id=identity("membership/" + asset_id), dataset_version_id=fixed.id,
                                                      asset_version_id=version.id, position=position))
            with database.read_session() as session:
                page = search_library(session, LibraryQuery(sort_by=sort_by, order=order))
            return [{"id": labels[item.entry_type, str(item.id)], "entry_type": item.entry_type} for item in page.items]
        finally:
            database.close()


def test_bin_compares_numeric_axes_and_descending_does_not_reverse_missing_partition():
    entries = [
        asset_entry("bin-10", parameters={"binning_x": 10, "binning_y": 1}),
        asset_entry("bin-2", parameters={"binning_x": 2, "binning_y": 1}),
        asset_entry("bin-1", parameters={"binning_x": 1, "binning_y": 2}),
        asset_entry("bin-missing", parameters={"binning_x": None, "binning_y": None}),
    ]
    assert [row["id"] for row in ordered(entries, "binning", "asc")] == ["bin-1", "bin-2", "bin-10", "bin-missing"]
    assert [row["id"] for row in ordered(entries, "binning", "desc")] == ["bin-10", "bin-2", "bin-1", "bin-missing"]


def test_iso_and_gain_groups_keep_fixed_order_and_put_missing_values_after_known_values():
    entries = [
        asset_entry("gain", parameters={"parameter_mode": "gain", "gain": 50, "offset": 2}),
        asset_entry("iso-missing", parameters={"parameter_mode": "iso", "iso": None}),
        asset_entry("unset", parameters={"parameter_mode": "standard"}),
        asset_entry("gain-missing", parameters={"parameter_mode": "gain", "gain": 50, "offset": None}),
        asset_entry("iso", parameters={"parameter_mode": "iso", "iso": 800}),
    ]
    assert [row["id"] for row in ordered(entries, "parameter_mode", "desc")] == [
        "iso", "iso-missing", "gain", "gain-missing", "unset",
    ]


def test_gain_sorts_without_offsets_and_offsets_only_break_equal_gain_ties():
    entries = [
        asset_entry("gain-100", parameters={"parameter_mode": "gain", "gain": 100, "offset": None}),
        asset_entry("gain-10", parameters={"parameter_mode": "gain", "gain": 10, "offset": None}),
        asset_entry("gain-50-offset-missing", parameters={"parameter_mode": "gain", "gain": 50, "offset": None}),
        asset_entry("gain-50-offset-known", parameters={"parameter_mode": "gain", "gain": 50, "offset": 2}),
    ]
    assert [row["id"] for row in ordered(entries, "parameter_mode", "asc")] == [
        "gain-10", "gain-50-offset-known", "gain-50-offset-missing", "gain-100",
    ]
    assert [row["id"] for row in ordered(entries, "parameter_mode", "desc")] == [
        "gain-100", "gain-50-offset-known", "gain-50-offset-missing", "gain-10",
    ]


def test_uniform_gain_datasets_sort_by_gain_while_mixed_and_unset_groups_stay_later():
    low = asset_entry("low", parameters={"parameter_mode": "gain", "gain": 10, "offset": None})
    high = asset_entry("high", parameters={"parameter_mode": "gain", "gain": 100, "offset": None})
    other = asset_entry("other", parameters={"parameter_mode": "gain", "gain": 50, "offset": 2})
    unset = asset_entry("unset-member", parameters={"parameter_mode": "standard", "gain": None, "offset": None})
    entries = [
        dataset_entry("high-set", [high, high]),
        dataset_entry("low-set", [low, low]),
        dataset_entry("mixed", [low, other]),
        dataset_entry("unset", [unset, unset]),
    ]
    assert [row["id"] for row in ordered(entries, "parameter_mode", "asc")] == [
        "low-set", "high-set", "mixed", "unset",
    ]
    assert [row["id"] for row in ordered(entries, "parameter_mode", "desc")] == [
        "high-set", "low-set", "mixed", "unset",
    ]


def test_dataset_uniform_mixed_partial_and_unset_values_stay_in_separate_partitions():
    light = asset_entry("light", classification={"frame_class": "subframe", "frame_type": "light"})
    dark = asset_entry("dark", classification={"frame_class": "subframe", "frame_type": "dark"})
    missing = asset_entry("missing", classification={"frame_class": None, "frame_type": None})
    known = asset_entry("known", classification={"frame_class": "masterframe", "frame_type": "dark"})
    entries = [
        dataset_entry("unset", [missing, missing]),
        dataset_entry("mixed", [light, dark]),
        dataset_entry("partial", [light, missing]),
        dataset_entry("uniform", [light, light]),
        known,
    ]
    for order in ("asc", "desc"):
        ids = [row["id"] for row in ordered(entries, "classification", order)]
        first_mixed = min(ids.index("mixed"), ids.index("partial"))
        assert ids.index("uniform") < first_mixed < ids.index("unset")
        assert ids.index("partial") == ids.index("mixed") + 1 or ids.index("mixed") == ids.index("partial") + 1


def test_equipment_sorts_by_display_name_and_equal_values_use_stable_record_identity():
    zulu = asset_entry("0001", parameters={"camera_id":"camera-a"})
    alpha = asset_entry("0002", parameters={"camera_id":"camera-b"})
    equal_asset = asset_entry("0000", name="same")
    equal_dataset = dataset_entry("0001", [asset_entry("member",name="same")])
    equal_dataset["dataset"]["name"]="same"
    zulu["asset"]["equipment_snapshot"] = {"camera_id": {"id": "camera-a", "name": "Zulu Camera"}}
    alpha["asset"]["equipment_snapshot"] = {"camera_id": {"id": "camera-b", "name": "alpha Camera"}}
    assert [row["id"] for row in ordered([zulu,alpha],"camera","asc")] == ["0002","0001"]
    assert [row["entry_type"] for row in ordered([equal_dataset,equal_asset],"name","asc")] == ["asset","dataset"]
