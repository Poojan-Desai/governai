import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from governai.control_evidence import run_control_evidence, write_control_evidence
from governai.pipeline import LocalPipeline


class ControlEvidenceTests(unittest.TestCase):
    def test_executed_controls_have_procedures_results_references_and_no_row_pii(self):
        report = run_control_evidence()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['summary'], {'executed':7,'passed':7})
        self.assertEqual(len({c['control_id'] for c in report['controls']}),7)
        for control in report['controls']:
            self.assertTrue(control['procedure']); self.assertTrue(control['evidence_references'])
            self.assertEqual(control['exceptions'],[])
            self.assertEqual(control['remediation_status'],'NO_EXCEPTION')
        payload=json.dumps(report)
        for forbidden in ['example.test','+1-555-','Synthetic Customer 00001','ACC-00001','CONTROL-ROLLBACK-NEW']:
            self.assertNotIn(forbidden,payload)
        self.assertEqual(sum(item['row_count'] for item in report['source_evidence']),105)

    def test_a_real_control_failure_is_reported_as_failure(self):
        # Simulate broken masking; do not let a green report be constant metadata.
        with patch.object(LocalPipeline,'mask_email',side_effect=lambda email: email):
            # Projection and comparison would both use the broken function; the
            # independent privacy requirement must also reject unmasked values.
            report=run_control_evidence()
        self.assertEqual(report['status'],'FAIL')
        privacy=next(c for c in report['controls'] if c['control_id']=='PRIV-001')
        self.assertEqual(privacy['result'],'FAIL')
        self.assertTrue(privacy['exceptions'])

    def test_written_report_has_verifiable_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'controls.json'
            report=write_control_evidence(path)
            self.assertEqual(json.loads(path.read_text()),report)
            self.assertEqual(path.with_suffix('.json.sha256').read_text().strip(),hashlib.sha256(path.read_bytes()).hexdigest())
