from pathlib import Path
from uuid import uuid4
import json, time, threading
import numpy as np
import psutil
from astropy.io import fits
import astrophotoflow
from astrophotoflow.config import Settings, ImportRoot
from astrophotoflow.backend.db import Database
from astrophotoflow.backend.models import AssetTask, AssetTaskItem, AssetVersion
from astrophotoflow.backend.schema import upgrade_database, database_lock
from astrophotoflow.backend import ingestion
from sqlalchemy import select, func

root = Path.cwd()
assert Path(astrophotoflow.__file__).is_relative_to(root), astrophotoflow.__file__
source = root / '.artifacts' / 'import-benchmark' / 'source'
source.mkdir(parents=True, exist_ok=True)
count = 8
for index in range(count):
    path = source / f'{index:02}.fits'
    if not path.exists():
        hdu = fits.PrimaryHDU(np.arange(2048*2048, dtype=np.float32).reshape(2048, 2048) + index * 100)
        hdu.header['IMAGETYP'] = 'Light Frame'
        hdu.writeto(path)
results = []
for trial in range(3):
    data = root / '.artifacts' / 'import-benchmark' / f'run-{uuid4()}'
    settings = Settings('127.0.0.1', 8190, data, ('http://127.0.0.1:8188',), (ImportRoot('science', source),))
    with database_lock(settings):
        upgrade_database(settings)
    database = Database(settings.database_path)
    task_id = str(uuid4())
    with database.write_session() as session:
        session.add(AssetTask(id=task_id, status='queued', sources=[{'root_id':'science','path':'','kind':'directory','enumeration_completed':False}], storage_mode='managed', classification={}, parameters={}, notes=None, dataset_name='benchmark', target_dataset_id=str(uuid4()), dataset_base_revision=None, dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None))
    process = psutil.Process()
    before_io = process.io_counters()
    start = time.perf_counter()
    registration = None
    visibility = None
    peak = process.memory_info().rss
    thread = threading.Thread(target=ingestion.process_task, args=(database,settings,task_id))
    thread.start()
    while thread.is_alive():
        with database.read_session() as session:
            task = session.get(AssetTask, task_id)
            registered = session.scalar(select(func.count()).select_from(AssetTaskItem).where(AssetTaskItem.task_id==task_id,AssetTaskItem.asset_version_id.is_not(None)))
            if registered == count and registration is None:
                registration = time.perf_counter()-start
            if task.dataset_id and visibility is None:
                visibility = time.perf_counter()-start
        peak = max(peak, process.memory_info().rss)
        time.sleep(.005)
    thread.join()
    total = time.perf_counter()-start
    after_io = process.io_counters()
    with database.read_session() as session:
        task = session.get(AssetTask,task_id)
        assert task.status == 'completed', (task.status,task.error)
        versions = session.scalars(select(AssetVersion)).all()
        assert len(versions)==count
        assert all(row.content_hash and row.availability=='available' for row in versions)
    results.append({'registration_seconds':registration or total,'dataset_visible_seconds':visibility or total,'total_seconds':total,'read_bytes':after_io.read_bytes-before_io.read_bytes,'write_bytes':after_io.write_bytes-before_io.write_bytes,'peak_rss_mb':peak/1024/1024})
    database.close()
print(json.dumps({'source':str(source),'files':count,'source_bytes':sum(p.stat().st_size for p in source.glob('*.fits')),'trials':results}, indent=2))
