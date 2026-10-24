"""Regression: published data and manifest must refer to one source capture."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from governai.generator import generate_sources
from governai.pipeline import LocalPipeline


class SourceSnapshotTests(unittest.TestCase):
    def test_replacement_after_read_cannot_change_rows_hash_or_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = generate_sources(root / 'sources', customer_count=4, account_count=5, transactions_per_month=2)
            pipeline = LocalPipeline(root / 'db.sqlite'); pipeline.initialize()
            path = generated.base_dir / 'customers.csv'
            expected = path.read_bytes()
            read_source = pipeline.read_source
            def capture_then_replace(source_path):
                captured = read_source(source_path)
                source_path.write_text('replacement,bytes\nwrong,source\n')
                return captured
            with patch.object(pipeline, 'read_source', side_effect=capture_then_replace):
                outcome = pipeline.ingest_customers(path)
            self.assertEqual(outcome.status, 'succeeded')
            self.assertEqual(outcome.source_sha256, hashlib.sha256(expected).hexdigest())
            with pipeline.connect() as db:
                manifest = db.execute('SELECT sha256,byte_size,row_count FROM source_manifests').fetchone()
                self.assertEqual(tuple(manifest), (hashlib.sha256(expected).hexdigest(),len(expected),4))
                self.assertEqual(db.execute('SELECT COUNT(*) FROM raw_customers').fetchone()[0],4)
                self.assertEqual(db.execute('SELECT full_name FROM raw_customers ORDER BY customer_id LIMIT 1').fetchone()[0],'Synthetic Customer 00001')

    def test_removed_file_after_capture_can_publish_and_replay_saved_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = generate_sources(root / 'sources', customer_count=4, account_count=5, transactions_per_month=2)
            pipeline = LocalPipeline(root / 'db.sqlite'); pipeline.initialize()
            path = generated.base_dir / 'customers.csv'
            source = pipeline.read_source(path)
            path.unlink()
            with patch.object(pipeline, 'read_source', return_value=source):
                first = pipeline.ingest_customers(path)
                second = pipeline.ingest_customers(path)
            self.assertEqual(first, second)
            self.assertEqual(first.accepted_rows,4)

    def test_decode_failure_creates_no_partial_control_or_data_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/'invalid.csv'; path.write_bytes(b'\xff\xfe\x00')
            pipeline=LocalPipeline(root/'db.sqlite'); pipeline.initialize()
            with self.assertRaises(UnicodeDecodeError): pipeline.ingest_customers(path)
            with pipeline.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM pipeline_runs').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM raw_customers').fetchone()[0],0)

    def test_process_termination_rolls_back_uncommitted_batch_then_restart_succeeds(self):
        import os
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            generated=generate_sources(root/'sources',customer_count=4,account_count=5,transactions_per_month=2)
            pipeline=LocalPipeline(root/'db.sqlite'); pipeline.initialize()
            pipeline.ingest_customers(generated.base_dir/'customers.csv')
            pipeline.ingest_accounts(generated.base_dir/'accounts.csv')
            marker=root/'loaded.marker'
            script='''import sys,time
from pathlib import Path
from governai.pipeline import LocalPipeline
class InterruptedPipeline(LocalPipeline):
    @staticmethod
    def load_transactions(db, rows, run_id):
        LocalPipeline.load_transactions(db, rows, run_id)
        Path(sys.argv[3]).write_text("raw-write-uncommitted")
        time.sleep(30)
pipeline=InterruptedPipeline(Path(sys.argv[1]))
pipeline.ingest_transactions(Path(sys.argv[2]))
'''
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
            child=subprocess.Popen([sys.executable,'-c',script,str(pipeline.database_path),str(generated.base_dir/'transactions.csv'),str(marker)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while not marker.exists() and child.poll() is None and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertTrue(marker.exists(),'child did not reach uncommitted write')
                child.kill(); child.communicate(timeout=5)
                restarted=LocalPipeline(pipeline.database_path); restarted.initialize()
                with restarted.connect() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM raw_transactions').fetchone()[0],0)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM pipeline_runs WHERE asset_id='source.card_transactions'").fetchone()[0],0)
                    self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                outcome=restarted.ingest_transactions(generated.base_dir/'transactions.csv')
                self.assertEqual((outcome.status,outcome.accepted_rows),('succeeded',12))
            finally:
                if child.poll() is None: child.kill(); child.communicate(timeout=5)
