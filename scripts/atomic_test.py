# Run: python scripts/atomic_test.py. A failed write must leave the old file whole and no temp file behind.
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'app'))
import atomic  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    f = Path(d) / 'draft_content.json'
    atomic.write_text(f, '{"v": 1}')
    assert f.read_text(encoding='utf-8') == '{"v": 1}'
    with mock.patch('os.fsync', side_effect=OSError('disk full')):
        try:
            atomic.write_text(f, '{"v": 2, "half": "written')
        except OSError:
            pass
        else:
            raise AssertionError('the failed write was swallowed')
    assert f.read_text(encoding='utf-8') == '{"v": 1}', 'old content lost'
    assert [p.name for p in Path(d).iterdir()] == ['draft_content.json'], 'temp file left behind'
    atomic.write_text(f, 'ไทย', encoding='utf-8-sig')
    assert f.read_bytes().startswith(b'\xef\xbb\xbf')
print('PASS atomic writes: replace in one step, old file kept on failure, no temp left, encoding kept')
