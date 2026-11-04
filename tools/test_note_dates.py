"""기기별 파일 생성일 대신 공유 머리말/갱신일을 쓰고 저장·복사 후에도 기준일을 유지한다."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

tmp = tempfile.TemporaryDirectory()
os.environ['APPDATA'] = tmp.name
Path(tmp.name, 'iamtalkernote').mkdir()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import store


class NoteDatesTest(unittest.TestCase):
    def test_fills_missing_dates_and_preserves_metadata(self):
        text = '---\nsource: https://example.com\ntags: [보존]\n---\n본문'
        result = store.ensure_dates(text, 1609502400, 1609588800)
        meta = store.parse_meta(result)
        self.assertEqual(meta['created'], 1609502400)
        self.assertEqual(meta['updated'], 1609588800)
        self.assertEqual(meta['tags'], ['보존'])
        self.assertTrue(result.endswith('본문'))
        self.assertEqual(store.ensure_dates(result, 1, 2), result)

    def test_no_header_and_creation_survives_save_and_copy(self):
        root = Path(tmp.name, 'vault'); root.mkdir(exist_ok=True)
        path = root / '옛 노트.md'; path.write_text('본문', encoding='utf-8')
        os.utime(path, (1609502400, 1609502400))
        repo = store.Store(str(root))
        self.assertEqual(repo.list_notes('*')[0]['ctime'], 1609502400)
        repo.save(str(path), '본문\n태그: #보존\n', touch=False)
        self.assertGreater(path.stat().st_mtime, 1609502400)  # 동기화 도구가 실제 파일 변경을 인식해야 한다.
        self.assertEqual(store.parse_meta(path.read_text(encoding='utf-8'))['updated'], 1609502400)
        self.assertEqual(store.parse_meta(path.read_text(encoding='utf-8'))['created'], 1609502400)
        copied = root / '복사 노트.md'; copied.write_bytes(path.read_bytes())
        self.assertEqual({n['ctime'] for n in repo.list_notes('*')}, {1609502400})
        repo.save(str(path), path.read_text(encoding='utf-8') + '\n편집', touch=True)
        self.assertEqual(store.parse_meta(path.read_text(encoding='utf-8'))['created'], 1609502400)

    def test_new_note_has_both_dates(self):
        root = Path(tmp.name, 'new'); root.mkdir(exist_ok=True)
        note = store.Store(str(root)).create_note('', '새 노트', '')
        meta = store.parse_meta(Path(note['path']).read_text(encoding='utf-8'))
        self.assertIsNotNone(meta['created']); self.assertEqual(meta['created'], meta['updated'])

    def test_restore_missing_original_preserves_supplied_creation(self):
        root = Path(tmp.name, 'restore'); root.mkdir(exist_ok=True)
        path = root / 'restored.md'
        store.Store(str(root)).save(str(path), store.ensure_dates('복원', 1609502400, 1609588800))
        self.assertEqual(store.parse_meta(path.read_text(encoding='utf-8'))['created'], 1609502400)


if __name__ == '__main__': unittest.main()
